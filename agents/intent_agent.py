"""
LLM-based intent classifier for user messages.
Returns intent (e.g. daily_prediction, general_question) and optional params (e.g. sign).
"""
import json
import re

from services.llm_service import call_llm

INTENT_PROMPT = """You are an intent classifier for an astrology/numerology chatbot. Given the user message, respond with exactly one JSON object (no markdown, no code fence) with:
- "intent": one of "daily_prediction", "general_question"
- "params": optional object, e.g. {{"sign": "virgo"}} only if the user explicitly mentions a zodiac sign (e.g. "for Virgo", "as a Leo"); otherwise omit or use {{}}

Use "daily_prediction" when the user asks for today's horoscope, daily prediction, daily forecast, what's in store today, or similar. Use "general_question" for anything else (follow-up, career, love, numbers, personality, etc.).

User message: {message}

JSON response:"""


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def classify(message: str) -> tuple[str, dict]:
    """
    Classify user message into intent and optional params.
    :param message: User's raw message.
    :return: (intent, params) e.g. ("daily_prediction", {"sign": "virgo"}) or ("general_question", {}).
    """
    if not (message or "").strip():
        return "general_question", {}
    prompt = INTENT_PROMPT.format(message=message.strip())
    response = call_llm(prompt)
    data = _extract_json(response)
    if not data or not isinstance(data, dict):
        return "general_question", {}
    intent = (data.get("intent") or "general_question").strip().lower()
    if intent not in ("daily_prediction", "general_question"):
        intent = "general_question"
    params = data.get("params")
    if not isinstance(params, dict):
        params = {}
    # Normalize sign to lowercase if present
    if params.get("sign"):
        params["sign"] = str(params["sign"]).strip().lower()
    return intent, params
