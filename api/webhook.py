import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from workers.celery_worker import process_message_task
from core.orchestrator import Orchestrator
from config import WASENDER_WEBHOOK_SECRET

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


def _extract_inbound_from_wasender(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """
    Parse Wasender event payload and return (phone, text) for inbound user messages.
    """
    event = str(payload.get("event") or "").strip().lower()
    if event not in {
        "messages.received",
        "messages.upsert",
        "messages.personal.received",
        "messages.group.received",
        "personal.message.received",
        "group.message.received",
    }:
        return (None, None, None)

    data = payload.get("data") or {}
    message_node = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(message_node, dict):
        return (None, None, None)

    key = message_node.get("key") or {}
    if not isinstance(key, dict):
        key = {}

    # Ignore echoes/outgoing messages on upsert streams.
    if key.get("fromMe") is True:
        return (None, None, None)

    text = str(message_node.get("messageBody") or "").strip()
    if not text:
        raw_msg = message_node.get("message") or {}
        if isinstance(raw_msg, dict):
            text = str(raw_msg.get("conversation") or "").strip()

    phone = (
        _normalize_phone(str(key.get("cleanedSenderPn") or ""))
        or _normalize_phone(str(key.get("cleanedParticipantPn") or ""))
        or _normalize_phone(str(key.get("senderPn") or ""))
    )

    if not phone or not text:
        return (None, None, None)
    message_id = str(key.get("id") or "").strip() or None
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
async def wasender_webhook(request: Request):
    """
    Wasender webhook endpoint.
    Expects JSON payload with data.messages.messageBody + sender fields.
    """
    signature = request.headers.get("X-Webhook-Signature", "").strip()
    if WASENDER_WEBHOOK_SECRET and signature != WASENDER_WEBHOOK_SECRET:
        return JSONResponse(status_code=401, content={"status": "unauthorized"})

    try:
        payload = await request.json()
    except Exception:
        raw = (await request.body()).decode(errors="ignore")
        logger.warning("Invalid Wasender webhook payload: %s", raw[:1000])
        return {"status": "ignored", "reason": "invalid_json"}

    if not isinstance(payload, dict):
        return {"status": "ignored", "reason": "invalid_payload"}

    phone, message, message_id = _extract_inbound_from_wasender(payload)
    if not phone or not message:
        # Non-message or unsupported event shape: ACK with 200 quickly.
        return {"status": "ignored"}
    if _is_duplicate_message(message_id):
        logger.info("Skipping duplicate inbound message id=%s", message_id)
        return {"status": "duplicate_ignored"}

    logger.info("Inbound webhook phone=%s msg_id=%s text=%r", phone, message_id, message)
    await Orchestrator().handle_message(phone, message)
    return {"status": "processed"}


@router.post("/simulate-message")
async def simulate_message(data: IncomingMsg):
    # process_message_task.delay(data.phone, data.message)
    logger.info("Simulated inbound phone=%s text=%r", data.phone, data.message)
    await Orchestrator().handle_message(data.phone, data.message)

    return {"status": "queued"}
