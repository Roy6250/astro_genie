"""
Mock WhatsApp service for testing via curl.
Messages are logged but not sent to any provider.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)
MAX_LOG_TEXT_CHARS = 800
MAX_SEND_TEXT_CHARS = 3500


def _normalize_to_e164(phone: str) -> str:
    """Normalize phone to E.164 format."""
    digits = re.sub(r"\D", "", str(phone or ""))
    if not digits:
        return ""
    return f"+{digits}"


def _for_log(text: str, limit: int = MAX_LOG_TEXT_CHARS) -> str:
    """Format text for logging with truncation."""
    clean = (text or "").replace("\n", "\\n")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "...<truncated>"


def send_whatsapp_message(phone: str, message: str) -> dict[str, Any]:
    """
    Mock WhatsApp send (logs only, no provider integration).
    Returns success response for testing.
    """
    to = _normalize_to_e164(phone)
    text = str(message or "").strip()
    
    if not to or not text:
        logger.warning("Skipping outbound message: missing phone or text.")
        return {"ok": False, "error": "missing phone or text"}
    
    if len(text) > MAX_SEND_TEXT_CHARS:
        logger.warning(
            "Outbound message too long (%d chars). Truncating to %d chars.",
            len(text),
            MAX_SEND_TEXT_CHARS,
        )
        text = text[: MAX_SEND_TEXT_CHARS - 20].rstrip() + "\n\n...[truncated]"
    
    logger.info("Mock outbound message to=%s text=%s", to, _for_log(text))
    
    return {"ok": True, "mock": True, "phone": to, "chars": len(text)}
