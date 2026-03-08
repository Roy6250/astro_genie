"""
Location enrichment utilities:
- LLM normalizes user-entered place into city/state/country style fields.
- ip-api lookup is attempted for domain/IP style queries.
- Fallback geocoding resolves regular place names to coordinates.
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from services.llm_service import call_llm
from integrations.prokerala.kundli import resolve_place as resolve_place_fallback

IP_API_BASE = "http://ip-api.com/json"
IP_API_FIELDS = "status,message,query,country,countryCode,region,regionName,city,zip,lat,lon,timezone"
logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any] | None:
    payload = (text or "").strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", payload)
        payload = re.sub(r"\n?```$", "", payload).strip()
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _normalize_place_with_llm(place: str) -> dict[str, Any]:
    prompt = f"""Normalize this place of birth into structured JSON.
Input: "{place}"

Return ONLY JSON with keys:
- normalized_place (string)
- city (string or "")
- state (string or "")
- country (string or "")
- likely_domain_or_ip (string or "")

Rules:
- Keep text concise, no extra words.
- If unknown, use empty string.
"""
    parsed = _extract_json(call_llm(prompt))
    if not parsed:
        return {
            "normalized_place": place.strip(),
            "city": "",
            "state": "",
            "country": "",
            "likely_domain_or_ip": "",
        }
    parsed.setdefault("normalized_place", place.strip())
    parsed.setdefault("city", "")
    parsed.setdefault("state", "")
    parsed.setdefault("country", "")
    parsed.setdefault("likely_domain_or_ip", "")
    return parsed


def _looks_like_ip_or_domain(query: str) -> bool:
    text = (query or "").strip()
    if not text:
        return False
    ip_re = r"^\d{1,3}(\.\d{1,3}){3}$"
    domain_re = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(ip_re, text) or re.match(domain_re, text))


def _ip_api_lookup(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"status": "fail", "message": "empty query"}
    url = f"{IP_API_BASE}/{quote(q)}?fields={quote(IP_API_FIELDS)}"
    req = Request(url, method="GET", headers={"User-Agent": "astro-genie/1.0"})
    with urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
    data = json.loads(raw)
    return data if isinstance(data, dict) else {"status": "fail", "message": "invalid response"}


def enrich_place(place: str) -> dict[str, Any]:
    """
    Enrich place string with structured fields + coordinates.
    Strategy:
    1) LLM normalizes city/state/country fields.
    2) ip-api lookup for domain/IP style input only.
    3) Fallback to regular geocoding for human place names.
    """
    raw = (place or "").strip()
    if not raw:
        return {"status": "error", "message": "Place is required"}

    normalized = _normalize_place_with_llm(raw)
    normalized_place = (normalized.get("normalized_place") or raw).strip()
    city = (normalized.get("city") or "").strip()
    state = (normalized.get("state") or "").strip()
    country = (normalized.get("country") or "").strip()
    domain_or_ip = (normalized.get("likely_domain_or_ip") or "").strip()
    logger.info(
        "Location enrich start raw=%r normalized=%r city=%r state=%r country=%r",
        raw,
        normalized_place,
        city,
        state,
        country,
    )

    # Try ip-api only when query is an IP/domain (API supports those reliably).
    ip_query = domain_or_ip if _looks_like_ip_or_domain(domain_or_ip) else (raw if _looks_like_ip_or_domain(raw) else "")
    if ip_query:
        try:
            ip_data = _ip_api_lookup(ip_query)
            if ip_data.get("status") == "success":
                logger.info("Location enrich success source=ip-api query=%r", ip_query)
                return {
                    "status": "ok",
                    "source": "ip-api",
                    "normalized_place": normalized_place,
                    "city": city or str(ip_data.get("city") or ""),
                    "state": state or str(ip_data.get("regionName") or ""),
                    "country": country or str(ip_data.get("country") or ""),
                    "latitude": ip_data.get("lat"),
                    "longitude": ip_data.get("lon"),
                    "timezone": str(ip_data.get("timezone") or "UTC"),
                    "ip_query": str(ip_data.get("query") or ip_query),
                }
        except Exception:
            pass

    # Fallback for regular place names (city/state/country text input).
    candidates: list[str] = []
    for val in [
        normalized_place,
        raw,
        f"{city}, {country}" if city and country else "",
        f"{city} {country}" if city and country else "",
        city,
    ]:
        q = " ".join((val or "").split()).strip(" ,")
        if q and q not in candidates:
            candidates.append(q)

    last_error = "Could not resolve location"
    geo = {}
    matched_query = ""
    for q in candidates:
        geo = resolve_place_fallback(q)
        if geo.get("status") == "ok":
            matched_query = q
            break
        last_error = str(geo.get("message") or last_error)
        logger.warning("Location geocode failed query=%r err=%s", q, last_error)

    if geo.get("status") != "ok":
        logger.warning("Location enrich failed raw=%r err=%s", raw, last_error)
        return {"status": "error", "message": last_error}

    logger.info("Location enrich success source=geocode-fallback query=%r", matched_query or normalized_place or raw)
    return {
        "status": "ok",
        "source": "geocode-fallback",
        "normalized_place": geo.get("place_name") or normalized_place or raw,
        "city": city,
        "state": state,
        "country": country,
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "timezone": geo.get("timezone") or "UTC",
        "ip_query": "",
        "matched_query": matched_query,
    }
