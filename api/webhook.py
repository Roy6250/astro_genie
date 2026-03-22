import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from core.orchestrator import Orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)
_SEEN_MESSAGE_IDS: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 300.0

class IncomingMsg(BaseModel):
    phone: str
    message: str


def _normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    return digits


def _extract_inbound_message(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """
    Generic message extraction (mock/mimicked webhook).
    Accepts flexible payload formats for testing.
    """
    phone = payload.get("phone")
    text = payload.get("message") or payload.get("text")
    message_id = payload.get("message_id") or payload.get("id")
    
    if not phone or not text:
        return (None, None, None)
    
    phone = _normalize_phone(str(phone))
    text = str(text).strip()
    message_id = str(message_id).strip() if message_id else None
    
    return (phone, text, message_id)


def _prune_seen_messages(now: float) -> None:
    expired = [k for k, ts in _SEEN_MESSAGE_IDS.items() if (now - ts) > _DEDUP_TTL_SECONDS]
    for key in expired:
        _SEEN_MESSAGE_IDS.pop(key, None)


def _is_duplicate_message(message_id: str | None) -> bool:
    if not message_id:
        return False
    now = time.monotonic()
    _prune_seen_messages(now)
    if message_id in _SEEN_MESSAGE_IDS:
        return True
    _SEEN_MESSAGE_IDS[message_id] = now
    return False


@router.get("/")
@router.get("/webhook")
async def webhook_health():
    return {"status": "ok"}


@router.post("/")
@router.post("/webhook")
async def webhook_handler(request: Request):
    """
    Generic webhook endpoint (mock/mimicked).
    Accepts flexible JSON payload with phone and message fields.
    """
    try:
        payload = await request.json()
    except Exception:
        raw = (await request.body()).decode(errors="ignore")
        logger.warning("Invalid webhook payload: %s", raw[:1000])
        return {"status": "ignored", "reason": "invalid_json"}

    if not isinstance(payload, dict):
        return {"status": "ignored", "reason": "invalid_payload"}

    phone, message, message_id = _extract_inbound_message(payload)
    if not phone or not message:
        logger.info("Ignoring incomplete webhook payload: phone=%s, message=%s", phone, message)
        return {"status": "ignored"}
    
    if _is_duplicate_message(message_id):
        logger.info("Skipping duplicate message id=%s", message_id)
        return {"status": "duplicate_ignored"}

    logger.info("Inbound message phone=%s msg_id=%s text=%r", phone, message_id, message)
    await Orchestrator().handle_message(phone, message)
    return {"status": "processed"}


@router.post("/simulate-message")
async def simulate_message(data: IncomingMsg):
    """
    Simulate an inbound message (testing endpoint, no WhatsApp integration).
    """
    logger.info("Simulated inbound phone=%s text=%r", data.phone, data.message)
    await Orchestrator().handle_message(data.phone, data.message)
    return {"status": "queued"}
