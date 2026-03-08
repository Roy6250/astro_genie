"""
Prokerala v2 Kundli integration with free place-to-coordinate resolution.

Flow:
- Resolve user-entered place via Open-Meteo geocoding (free, no API key)
- Build ISO datetime with zone offset from resolved timezone
- Call Prokerala detailed astrology endpoints:
  - kundli
  - dasha-periods
  - mangal-dosha
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import urllib.error

from zoneinfo import ZoneInfo

from integrations.prokerala.auth import get_access_token
from services.llm_service import call_llm

BASE_URL = "https://api.prokerala.com/v2"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
KUNDLI_ENDPOINT = "/astrology/kundli"
DASHA_ENDPOINT = "/astrology/dasha-periods"
MANGAL_DOSHA_ENDPOINT = "/astrology/mangal-dosha"
MANGAL_DOSHA_ADV_ENDPOINT = "/astrology/mangal-dosha-advanced"

logger = logging.getLogger(__name__)


def _http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    req = Request(url, method="GET", headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    return json.loads(raw)


def _error_from_http_exception(exc: urllib.error.HTTPError) -> dict[str, Any]:
    body = exc.read().decode() if exc.fp else ""
    try:
        err = json.loads(body)
        errors = err.get("errors") if isinstance(err, dict) else None
        if isinstance(errors, list) and errors:
            details = []
            for item in errors:
                if isinstance(item, dict):
                    detail = str(item.get("detail") or item.get("title") or "").strip()
                    if detail:
                        details.append(detail)
            msg = " | ".join(details) if details else (err.get("message", "") if isinstance(err, dict) else "")
        else:
            msg = err.get("message", "") if isinstance(err, dict) else ""
        if not msg:
            msg = body or str(exc)
        return {"status": "error", "message": msg, "details": err}
    except Exception:
        return {"status": "error", "message": body or str(exc)}


def resolve_place(place: str) -> dict[str, Any]:
    """
    Resolve a place name to coordinates using Open-Meteo geocoding.
    Returns {status, latitude, longitude, timezone, place_name} or {status:error, message}.
    """
    name = (place or "").strip()
    if not name:
        return {"status": "error", "message": "Place is required."}

    query = urlencode({"name": name, "count": 1, "language": "en", "format": "json"})
    url = f"{GEOCODE_URL}?{query}"
    try:
        data = _http_get_json(url, headers={"User-Agent": "astro-genie/1.0"})
    except Exception as exc:
        return {"status": "error", "message": f"Location lookup failed: {exc}"}

    results = data.get("results") or []
    if not results:
        return {"status": "error", "message": f"Could not resolve location: {name}"}

    first = results[0] or {}
    lat = first.get("latitude")
    lon = first.get("longitude")
    tz = (first.get("timezone") or "").strip()
    place_name = (first.get("name") or name).strip()
    country = (first.get("country") or "").strip()
    admin1 = (first.get("admin1") or "").strip()
    pretty_parts = [p for p in [place_name, admin1, country] if p]
    pretty_name = ", ".join(dict.fromkeys(pretty_parts)) if pretty_parts else name

    if lat is None or lon is None:
        return {"status": "error", "message": f"Missing coordinates for location: {name}"}

    return {
        "status": "ok",
        "latitude": float(lat),
        "longitude": float(lon),
        "timezone": tz or "UTC",
        "place_name": pretty_name,
    }


def _build_iso_datetime_with_offset(date_of_birth: str, time_of_birth: str, timezone_name: str) -> str:
    """
    Build ISO 8601 datetime with numeric offset using resolved IANA timezone.
    """
    dt_local = datetime.strptime(f"{date_of_birth} {time_of_birth}", "%Y-%m-%d %H:%M")
    tz = ZoneInfo(timezone_name or "UTC")
    dt_with_tz = dt_local.replace(tzinfo=tz)
    return dt_with_tz.isoformat()


def _normalize_ayanamsa(ayanamsa: str | int | None) -> str:
    if ayanamsa is None or str(ayanamsa).strip() == "":
        return "1"  # default: Lahiri
    raw_ayanamsa = str(ayanamsa).strip().lower()
    name_to_code = {"lahiri": "1", "raman": "3", "kp": "5"}
    return name_to_code.get(raw_ayanamsa, raw_ayanamsa)


def _normalize_language(language: str | None = None, la: str | None = None) -> str | None:
    # API docs refer to `la` query param. Keep compatibility with existing `language` arg.
    chosen = (la or language or "").strip().lower()
    if not chosen:
        return None
    allowed = {"en", "hi", "ta", "ml"}
    return chosen if chosen in allowed else None


def _call_prokerala_astrology(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    query = urlencode(params, quote_via=quote)
    url = f"{BASE_URL}{endpoint}?{query}"
    try:
        return {"status": "ok", "data": _http_get_json(url, headers=headers, timeout=30)}
    except urllib.error.HTTPError as exc:
        return _error_from_http_exception(exc)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _prepare_profile_inputs(
    date_of_birth: str,
    time_of_birth: str,
    place: str,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    ayanamsa: str | int | None = None,
    language: str | None = None,
    la: str | None = None,
    year_length: int | str | None = None,
) -> dict[str, Any]:
    dob = (date_of_birth or "").strip()
    tob = (time_of_birth or "").strip() or "12:00"
    if not dob:
        return {"status": "error", "message": "Missing required argument: date_of_birth (YYYY-MM-DD)"}

    lat = latitude
    lon = longitude
    tz_name = (timezone or "").strip()
    resolved_place = (place or "").strip()

    if lat is None or lon is None:
        geo = resolve_place(place)
        if geo.get("status") != "ok":
            return geo
        lat = geo["latitude"]
        lon = geo["longitude"]
        if not tz_name:
            tz_name = geo.get("timezone") or "UTC"
        resolved_place = geo.get("place_name") or resolved_place

    if not tz_name:
        tz_name = "UTC"

    try:
        iso_datetime = _build_iso_datetime_with_offset(dob, tob, tz_name)
    except Exception as exc:
        return {"status": "error", "message": f"Invalid date/time/timezone: {exc}"}

    ayanamsa_value = _normalize_ayanamsa(ayanamsa)
    coordinates = f"{float(lat):.6f},{float(lon):.6f}"
    la_value = _normalize_language(language=language, la=la)
    try:
        year_length_value = int(year_length) if year_length is not None else 1
    except (TypeError, ValueError):
        return {"status": "error", "message": "Invalid year_length. Allowed values: 0 or 1"}
    if year_length_value not in (0, 1):
        return {"status": "error", "message": "Invalid year_length. Allowed values: 0 or 1"}

    common_params: dict[str, str] = {
        "datetime": iso_datetime,
        "coordinates": coordinates,
        "ayanamsa": ayanamsa_value,
    }
    if la_value:
        common_params["la"] = la_value

    return {
        "status": "ok",
        "common_params": common_params,
        "meta": {
            "requested_place": place,
            "resolved_place": resolved_place,
            "latitude": lat,
            "longitude": lon,
            "timezone": tz_name,
            "datetime": iso_datetime,
            "ayanamsa": ayanamsa_value,
            "la": la_value,
            "year_length": year_length_value,
        },
    }


def get_kundli(
    date_of_birth: str,
    time_of_birth: str,
    place: str,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    ayanamsa: str | int | None = None,
    language: str | None = None,
    la: str | None = None,
    year_length: int | str | None = None,
    include_dasha_periods: bool = True,
    include_mangal_dosha: bool = True,
) -> dict[str, Any]:
    """
    Fetch Kundli data from Prokerala.

    Required: date_of_birth (YYYY-MM-DD), time_of_birth (HH:MM), place (or latitude+longitude).
    If coordinates are not given, place is resolved via Open-Meteo geocoding.
    """
    prep = _prepare_profile_inputs(
        date_of_birth=date_of_birth,
        time_of_birth=time_of_birth,
        place=place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        ayanamsa=ayanamsa,
        language=language,
        la=la,
        year_length=year_length,
    )
    if prep.get("status") != "ok":
        return prep
    common_params = prep["common_params"]
    meta = prep["meta"]
    year_length_value = int(meta.get("year_length", 1))

    # 1) Base Kundli
    kundli_res = _call_prokerala_astrology(KUNDLI_ENDPOINT, common_params)
    if kundli_res.get("status") != "ok":
        return kundli_res

    result_data: dict[str, Any] = {"kundli": kundli_res.get("data")}

    # 2) Dasha periods (year_length supported)
    if include_dasha_periods:
        dasha_params = dict(common_params)
        dasha_params["year_length"] = str(year_length_value)
        dasha_res = _call_prokerala_astrology(DASHA_ENDPOINT, dasha_params)
        if dasha_res.get("status") == "ok":
            result_data["dasha_periods"] = dasha_res.get("data")
        else:
            result_data["dasha_periods_error"] = dasha_res.get("message")

    # 3) Mangal dosha details
    if include_mangal_dosha:
        mangal_params = dict(common_params)
        mangal_res = _call_prokerala_astrology(MANGAL_DOSHA_ENDPOINT, mangal_params)
        if mangal_res.get("status") == "ok":
            result_data["mangal_dosha"] = mangal_res.get("data")
        else:
            result_data["mangal_dosha_error"] = mangal_res.get("message")

    return {
        "status": "ok",
        "meta": meta,
        "data": result_data,
    }


def get_dasha_details(
    date_of_birth: str,
    time_of_birth: str,
    place: str,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    ayanamsa: str | int | None = None,
    la: str | None = None,
    year_length: int | str | None = None,
) -> dict[str, Any]:
    prep = _prepare_profile_inputs(
        date_of_birth=date_of_birth,
        time_of_birth=time_of_birth,
        place=place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        ayanamsa=ayanamsa,
        la=la,
        year_length=year_length,
    )
    if prep.get("status") != "ok":
        return prep

    common_params = prep["common_params"]
    meta = prep["meta"]
    dasha_params = dict(common_params)
    dasha_params["year_length"] = str(meta.get("year_length", 1))
    dasha_res = _call_prokerala_astrology(DASHA_ENDPOINT, dasha_params)
    if dasha_res.get("status") != "ok":
        return dasha_res

    dasha = (dasha_res.get("data") or {}).get("data") or {}
    return {"status": "ok", "meta": meta, "data": dasha}


def get_mangal_dosha_details(
    date_of_birth: str,
    time_of_birth: str,
    place: str,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    ayanamsa: str | int | None = None,
    la: str | None = None,
) -> dict[str, Any]:
    prep = _prepare_profile_inputs(
        date_of_birth=date_of_birth,
        time_of_birth=time_of_birth,
        place=place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        ayanamsa=ayanamsa,
        la=la,
    )
    if prep.get("status") != "ok":
        return prep

    common_params = prep["common_params"]
    meta = prep["meta"]
    mangal_res = _call_prokerala_astrology(MANGAL_DOSHA_ADV_ENDPOINT, common_params)
    endpoint_used = MANGAL_DOSHA_ADV_ENDPOINT
    if mangal_res.get("status") != "ok":
        logger.warning("Advanced mangal dosha endpoint failed, falling back to basic endpoint.")
        fallback = _call_prokerala_astrology(MANGAL_DOSHA_ENDPOINT, common_params)
        if fallback.get("status") != "ok":
            return mangal_res
        mangal_res = fallback
        endpoint_used = MANGAL_DOSHA_ENDPOINT

    mangal = (mangal_res.get("data") or {}).get("data") or {}
    out_meta = dict(meta)
    out_meta["mangal_endpoint_used"] = endpoint_used
    return {"status": "ok", "meta": out_meta, "data": mangal}


def _safe_preview(payload: Any, max_chars: int = 1600) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=True, default=str)
    except Exception:
        raw = str(payload)
    raw = raw.strip()
    if len(raw) <= max_chars:
        return raw
    return raw[: max_chars - 18] + "...(truncated)"


def _shared_llm_formatter(kind: str, meta: dict[str, Any], summary: dict[str, Any], raw_data: Any) -> str:
    place = meta.get("resolved_place", meta.get("requested_place", "Unknown"))
    birth_dt = meta.get("datetime", "Unknown")
    prompt = (
        "Task:\n"
        "Rewrite astrology API output into a WhatsApp-friendly human explanation.\n\n"
        "Output contract:\n"
        "- Keep it under 170 words\n"
        "- Warm, clear, and practical tone\n"
        "- No JSON and no technical jargon\n"
        "- Include exactly these sections in this order:\n"
        "  1) One-line headline\n"
        "  2) What this means for you\n"
        "  3) Practical guidance\n"
        "  4) Gentle caution\n"
        "- End with one short next-step prompt.\n\n"
        f"Context:\n- Type: {kind}\n- Place: {place}\n- Birth datetime: {birth_dt}\n"
        f"- Structured summary: {_safe_preview(summary, 1100)}\n"
        f"- Raw API preview: {_safe_preview(raw_data, 1300)}\n"
    )
    try:
        text = call_llm(prompt).strip()
        if text:
            return text[:1400].strip()
    except Exception as exc:
        logger.warning("LLM formatting failed kind=%s err=%s", kind, exc)

    # deterministic fallback
    lines = [
        f"✨ {kind.replace('_', ' ').title()}",
        f"📍 Based on: {place}",
        f"🕒 Birth datetime: {birth_dt}",
        f"What this means: {_safe_preview(summary, 320)}",
        "Practical guidance: Stay consistent with routine actions and avoid rushed decisions.",
        "Would you like a deeper step-by-step explanation?",
    ]
    return "\n".join(lines)[:1400].strip()


def format_dasha_response(result: dict[str, Any]) -> str:
    if result.get("status") != "ok":
        return result.get("message", "Could not fetch dasha details right now.")
    meta = result.get("meta") or {}
    data = result.get("data") or {}
    current = data.get("current_dasha") or {}
    summary = {
        "current_dasha_name": str(current.get("name") or "").strip() or "Not available",
        "current_dasha_start": str(current.get("start") or "").strip() or None,
        "current_dasha_end": str(current.get("end") or "").strip() or None,
        "current_antardasha": str((current.get("antardasha") or {}).get("name") or "").strip() or None,
        "next_dasha": str(((data.get("dasha_periods") or [{}])[1] if isinstance(data.get("dasha_periods"), list) and len(data.get("dasha_periods")) > 1 else {}).get("name") or "").strip() or None,
    }
    return _shared_llm_formatter("dasha_detail", meta, summary, data)


def format_mangal_dosha_response(result: dict[str, Any]) -> str:
    if result.get("status") != "ok":
        return result.get("message", "Could not fetch mangal dosha details right now.")
    meta = result.get("meta") or {}
    data = result.get("data") or {}
    has_dosha = data.get("has_dosha", data.get("is_manglik", data.get("dosha_present")))
    description = str(data.get("description") or data.get("interpretation") or "").strip()
    remedies = data.get("remedies") if isinstance(data.get("remedies"), list) else []
    summary = {
        "mangal_dosha_status": "Present" if has_dosha is True else ("Not present" if has_dosha is False else "Unknown"),
        "severity": str(data.get("severity") or "").strip() or None,
        "description": description[:250] if description else None,
        "top_remedy": str(remedies[0]).strip() if remedies else None,
        "endpoint_used": meta.get("mangal_endpoint_used"),
    }
    return _shared_llm_formatter("mangal_dosha_detail", meta, summary, data)


def format_kundli_response(result: dict[str, Any]) -> str:
    """
    Format Kundli response for MCP text output.
    """
    if result.get("status") != "ok":
        return result.get("message", "Could not fetch kundli data right now.")

    meta = result.get("meta") or {}
    payload = result.get("data") or {}
    kundli = ((payload.get("kundli") or {}).get("data") or {})
    details = (kundli.get("nakshatra_details") or {})

    nak = ((details.get("nakshatra") or {}).get("name") or "N/A")
    chandra = ((details.get("chandra_rasi") or {}).get("name") or "N/A")
    soorya = ((details.get("soorya_rasi") or {}).get("name") or "N/A")
    zodiac = ((details.get("zodiac") or {}).get("name") or "N/A")

    mangal = ((payload.get("mangal_dosha") or {}).get("data") or {})
    has_mangal = mangal.get("has_dosha")
    mangal_desc = str(mangal.get("description") or "").strip()
    mangal_line = "Not available"
    if isinstance(has_mangal, bool):
        mangal_line = "Present" if has_mangal else "Not present"
    if mangal_desc:
        mangal_line = f"{mangal_line} — {mangal_desc[:180]}"

    dasha = ((payload.get("dasha_periods") or {}).get("data") or {})
    current_dasha = dasha.get("current_dasha") or {}
    current_name = str(current_dasha.get("name") or "").strip()
    current_end = str(current_dasha.get("end") or "").strip()
    if current_name:
        dasha_line = f"{current_name}" + (f" (till {current_end})" if current_end else "")
    else:
        # Fallback to first period if structure differs
        periods = dasha.get("dasha_periods") or []
        first = periods[0] if isinstance(periods, list) and periods else {}
        first_name = str((first or {}).get("name") or "").strip()
        first_end = str((first or {}).get("end") or "").strip()
        dasha_line = first_name + (f" (till {first_end})" if first_name and first_end else "") if first_name else "Not available"

    summary = {
        "nakshatra": nak,
        "chandra_rasi": chandra,
        "soorya_rasi": soorya,
        "zodiac": zodiac,
        "current_dasha": dasha_line,
        "mangal_dosha": mangal_line,
    }
    return _shared_llm_formatter("kundli_overview", meta, summary, payload)
