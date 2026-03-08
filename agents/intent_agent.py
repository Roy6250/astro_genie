"""
LLM-based intent classifier for user messages.
Returns intent and optional params.
"""
import json
import re

from services.llm_service import call_llm

INTENT_PROMPT = """Task:
Classify the user message into exactly one intent.

Allowed intents:
- "daily_prediction"
- "kundli_generation"
- "dasha_detail"
- "mangal_dosha_detail"
- "general_question"

Output contract:
Return exactly one JSON object (no markdown, no extra text):
{{
  "intent": "<one of allowed intents>",
  "params": {{}}
}}

Decision rules:
- Use "daily_prediction" for today's horoscope / daily forecast asks.
- Use "kundli_generation" for asks to create/generate/read kundli or birth chart.
- Use "dasha_detail" for asks specifically about dasha periods/mahadasha/antardasha explanation.
- Use "mangal_dosha_detail" for asks specifically about mangal dosha / kuja dosha explanation.
- Use "general_question" for everything else.
- If user asks both kundli generation and dasha/mangal details together, choose:
  - "kundli_generation" if chart is not yet requested/generated in this message
  - otherwise the specific detail intent.

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
    # Fast keyword route for reliability
    lowered = message.strip().lower()
    if "mangal dosha" in lowered or "kuja dosha" in lowered:
        return "mangal_dosha_detail", {}
    if "dasha" in lowered or "mahadasha" in lowered or "antardasha" in lowered:
        return "dasha_detail", {}
    if any(k in lowered for k in ("kundli", "janam kundli", "birth chart")):
        return "kundli_generation", {}
    if any(k in lowered for k in ("daily prediction", "daily horoscope", "today horoscope", "today's horoscope", "daily forecast")):
        return "daily_prediction", {}
    prompt = INTENT_PROMPT.format(message=message.strip())
    response = call_llm(prompt)
    data = _extract_json(response)
    if not data or not isinstance(data, dict):
        return "general_question", {}
    intent = (data.get("intent") or "general_question").strip().lower()
    if intent not in ("daily_prediction", "kundli_generation", "dasha_detail", "mangal_dosha_detail", "general_question"):
        intent = "general_question"
    params = data.get("params")
    if not isinstance(params, dict):
        params = {}
    # Normalize sign to lowercase if present
    if params.get("sign"):
        params["sign"] = str(params["sign"]).strip().lower()
    return intent, params
