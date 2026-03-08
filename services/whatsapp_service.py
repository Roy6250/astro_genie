from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

from config import WASENDER_API_BASE_URL, WASENDER_API_KEY

logger = logging.getLogger(__name__)
MAX_LOG_TEXT_CHARS = 800
MAX_SEND_TEXT_CHARS = 3500


def _normalize_to_e164(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if not digits:
        return ""
    # Wasender docs expect E.164. Prefix '+' if missing.
    return f"+{digits}"


def _for_log(text: str, limit: int = MAX_LOG_TEXT_CHARS) -> str:
    clean = (text or "").replace("\n", "\\n")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "...<truncated>"


def send_whatsapp_message(phone: str, message: str) -> dict[str, Any]:
    """
    Send outbound WhatsApp text message via Wasender API.
    """
    to = _normalize_to_e164(phone)
    text = str(message or "").strip()
    if not to or not text:
        logger.warning("Skipping outbound message: missing phone or text.")
        return {"ok": False, "error": "missing phone or text"}
    if len(text) > MAX_SEND_TEXT_CHARS:
        logger.warning(
            "Outbound message too long (%d chars). Truncating to %d chars for provider compatibility.",
            len(text),
            MAX_SEND_TEXT_CHARS,
        )
        text = text[: MAX_SEND_TEXT_CHARS - 20].rstrip() + "\n\n...[truncated]"

    if not WASENDER_API_KEY:
        logger.warning("WASENDER_API_KEY not configured. Outbound message not sent.")
        logger.info("Fallback outbound [%s]: %s", to, text)
        return {"ok": False, "error": "wasender api key not configured"}

    url = f"{WASENDER_API_BASE_URL.rstrip('/')}/api/send-message"
    headers = {
        "Authorization": f"Bearer {WASENDER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"to": to, "text": text}
    logger.info("Outbound WhatsApp message to=%s text=%s", to, _for_log(text))

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=20)

            # Handle provider rate limiting with bounded retry/backoff.
            if resp.status_code == 429:
                retry_after_raw = resp.headers.get("Retry-After", "").strip()
                try:
                    retry_after = float(retry_after_raw) if retry_after_raw else 1.0
                except ValueError:
                    retry_after = 1.0
                wait_seconds = min(max(retry_after, 0.2), 3.0)
                if attempt < max_attempts:
                    logger.warning(
                        "Wasender rate-limited outbound to %s (attempt %d/%d). Retrying in %.1fs",
                        to,
                        attempt,
                        max_attempts,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue
                logger.warning("Wasender rate limit persisted for %s: %s", to, resp.text)
                return {"ok": False, "error": "rate_limited", "details": resp.text}

            resp.raise_for_status()
            body = resp.json()
            ok = bool(body.get("success", True))
            if not ok:
                logger.error("Wasender rejected message to %s: %s", to, body)
                return {"ok": False, "error": body.get("message", "send failed"), "provider": body}
            logger.info("Wasender message submitted to=%s status=%s", to, body.get("data", {}).get("status"))
            return {"ok": True, "provider": body}
        except requests.HTTPError:
            details = resp.text if "resp" in locals() else ""
            logger.exception("Wasender HTTP error while sending to %s details=%s", to, _for_log(details, 1200))
            return {"ok": False, "error": "http error", "details": details}
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message to %s", to)
            return {"ok": False, "error": str(exc)}

    return {"ok": False, "error": "send_failed"}
