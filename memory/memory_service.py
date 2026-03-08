"""
Phone-scoped memory service.
- Short-term memory: append-only conversational snippets.
- Long-term memory: curated durable facts (key/value).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.llm_service import call_llm

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict[str, Any] | None:
    payload = (text or "").strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", payload)
        payload = re.sub(r"\n?```$", "", payload).strip()
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


class MemoryService:
    def __init__(self, mongo):
        self.mongo = mongo

    def store_short(self, phone: str, role: str, content: str, tags: list[str] | None = None):
        text = str(content or "").strip()
        if not text:
            return
        self.mongo.store_short_memory(phone, role, text, tags=tags or [])

    def maybe_store_long(self, phone: str, role: str, content: str):
        text = str(content or "").strip()
        if not text:
            return
        # Keep extraction cheap and focused on user durable facts.
        if role != "user":
            return
        if len(text) < 20 and not any(k in text.lower() for k in ("my ", "i am", "i'm", "i prefer", "my name", "born", "dob")):
            return
        prompt = f"""Extract durable user facts from this {role} message.
Return STRICT JSON only:
{{
  "facts": [
    {{"key": "preferred_name", "value": "Ananya", "confidence": 0.9}}
  ]
}}

Rules:
- Keep only durable facts (name, location, preferences, stable goals, important constraints).
- Ignore temporary chit-chat.
- Use short snake_case keys.
- If no durable facts, return {{"facts":[]}}.

Message: {text}
"""
        try:
            data = _extract_json(call_llm(prompt)) or {"facts": []}
            facts = data.get("facts") if isinstance(data, dict) else []
            if not isinstance(facts, list):
                return
            for fact in facts[:8]:
                if not isinstance(fact, dict):
                    continue
                key = str(fact.get("key") or "").strip().lower()
                value = str(fact.get("value") or "").strip()
                confidence = fact.get("confidence", 0.7)
                try:
                    confidence = float(confidence)
                except Exception:
                    confidence = 0.7
                if not key or not value:
                    continue
                self.mongo.upsert_long_memory(
                    phone=phone,
                    key=key,
                    value=value,
                    source=role,
                    confidence=max(0.0, min(1.0, confidence)),
                )
        except Exception as exc:
            logger.warning("Long-memory extraction failed phone=%s err=%s", phone, exc)

    def get_memory_context(self, phone: str, short_limit: int = 8, long_limit: int = 15) -> str:
        short_items = self.mongo.get_short_memory(phone, limit=short_limit)
        long_items = self.mongo.get_long_memory(phone, limit=long_limit)
        lines: list[str] = []

        if long_items:
            lines.append("Long-term memory:")
            for item in long_items:
                k = str(item.get("key") or "")
                v = str(item.get("value") or "")
                if k and v:
                    lines.append(f"- {k}: {v}")
            lines.append("")

        if short_items:
            lines.append("Recent short-term memory:")
            for item in reversed(short_items):
                role = str(item.get("role") or "user")
                content = str(item.get("content") or "")
                if content:
                    lines.append(f"- {role}: {content[:220]}")

        return "\n".join(lines).strip()
