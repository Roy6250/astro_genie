import json
import logging
import re
from typing import Any

from llama_index.core import (
    Settings,
    PromptTemplate,
)
from utils.custom_llm import OurLLM

from models.numero_model import (
    CalculatedFrom,
    LuckyColor,
    LuckyDay,
    LuckyStone,
    NumerologyReading,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
#   Core calculation functions (pure Python)
# ────────────────────────────────────────────────

def calculate_life_path_number(dob: str) -> int:
    """Pythagorean Life Path Number (digital root of full date)"""
    digits = [int(c) for c in dob if c.isdigit()]
    total = sum(digits)
    while total > 9 and total not in (11, 22, 33):  # keep common master numbers
        total = sum(int(d) for d in str(total))
    return total if total != 0 else 9


def calculate_mulank(day: int) -> int:
    """Vedic Psychic Number / Mulank = day of birth reduced"""
    try:
        while day > 9:
            day = sum(int(d) for d in str(day))
        return day if day != 0 else 9
    except:
        return -1  # invalid


def calculate_destiny_number(name: str) -> int:
    """Pythagorean Destiny Number from full name"""
    name = name.upper().replace(" ", "")
    letter_values = {chr(i): i - 64 for i in range(65, 91)}  # A=1 to Z=26
    total = sum(letter_values.get(c, 0) for c in name)
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(d) for d in str(total))
    return total if total != 0 else 9


def get_number_traits(number: int) -> str:
    """Shared traits lookup for both Life Path & Mulank"""
    traits = {
        1: "independent, pioneering, leadership-oriented, original",
        2: "cooperative, diplomatic, sensitive, peacemaker",
        3: "creative, expressive, sociable, optimistic",
        4: "practical, disciplined, hardworking, stable",
        5: "adventurous, adaptable, freedom-loving, curious",
        6: "responsible, nurturing, harmonious, family-oriented",
        7: "analytical, introspective, spiritual, intellectual",
        8: "ambitious, powerful, material success driven, authoritative",
        9: "compassionate, humanitarian, idealistic, generous",
    }
    return traits.get(number, "unique / non-standard vibration")


def parse_dob_from_profile(dob_str: str) -> tuple[int, int, int] | None:
    """Parse DOB string to (day, month, year). Supports DD-MM-YYYY and YYYY-MM-DD."""
    if not dob_str or not isinstance(dob_str, str):
        return None
    digits = re.findall(r"\d+", dob_str)
    if len(digits) < 3:
        return None
    # Try DD-MM-YYYY (first part <= 31, second <= 12)
    d, m, y = int(digits[0]), int(digits[1]), int(digits[2])
    if 1 <= d <= 31 and 1 <= m <= 12 and y > 1900 and y < 2100:
        if d <= 12 and m <= 12 and (d > 12 or m > 12):
            # Ambiguous: could be DD-MM or MM-DD; prefer DD-MM-YYYY if first > 12
            pass
        return (d, m, y)
    # Try YYYY-MM-DD
    if 1900 <= d <= 2100 and 1 <= m <= 12 and 1 <= y <= 31:
        return (y, m, d)  # year, month, day -> (day, month, year)
    return None


# ────────────────────────────────────────────────
#   LLM & Settings
# ────────────────────────────────────────────────

llm = OurLLM()
Settings.llm = llm


# ────────────────────────────────────────────────
#   EXTRACTION PROMPT
# ────────────────────────────────────────────────

EXTRACTION_PROMPT = PromptTemplate(
    """
Extract the birth day, month, year, name, and place from the following user message.
Handle various date formats and normalize to numbers.

Output strictly in JSON format: {{"day": 15, "month": 3, "year": 1995, "name": "Sayantan Roy", "place": "Bengaluru"}}

Use null for missing fields.

User message: {query_str}
"""
)


# ────────────────────────────────────────────────
#   STRUCTURED JSON GENERATION PROMPT
# ────────────────────────────────────────────────

STRUCTURED_GENERATION_PROMPT = PromptTemplate(
    """
You are a warm, modern numerology and Vedic astrology guide. Based on the numbers below, output a single JSON object only. No markdown, no code fences, no extra text — only valid JSON.

Calculated numbers:
- Mulank (Psychic Number): {mulank} — traits: {mulank_traits}
- Life Path Number: {life_path} — traits: {life_path_traits}
{destiny_info}

Output a JSON object with exactly these keys (use null where optional):

- "lucky_numbers": array of 3–5 integers (1–9), include core numbers + 2–3 related; e.g. [3, 5, 6, 9]
- "today_vibe_number": one integer 1–9 for today's vibe or null
- "lucky_colors": array of objects with "name" and "reason" (e.g. {{"name": "emerald green", "reason": "Jupiter's glow"}})
- "lucky_days": array of objects with "day" and "reason" (e.g. {{"day": "Wednesday", "reason": "Mercury"}})
- "lucky_stone": object with "name" and "explanation"
- "power_phrase": string (e.g. "The Starlit Storyteller")
- "quick_tip": string (one short actionable tip)
- "follow_up_question": string (e.g. "Want me to check your personal year?")
- "personality_summary": string or null (optional)
- "main_challenge": string or null (optional)
- "suggested_follow_ups": array of strings (e.g. ["personal year", "love compatibility"]) or empty array

Be creative but keep values concise. Respond with only the JSON object.

"""
)


# ────────────────────────────────────────────────
#   Display formatter (single source of truth: JSON → message)
# ────────────────────────────────────────────────


def format_numerology_message(reading: NumerologyReading | dict) -> str:
    """Build user-facing message from structured reading (bullet-style, emoji-rich)."""
    if isinstance(reading, NumerologyReading):
        r = reading.model_dump(mode="json")
    else:
        r = reading

    lines = [
        "✨ Your Numerology Vibes ✨",
        "",
        f"🔢 Life Path: {r['life_path_number']} · Mulank: {r['mulank']}",
    ]
    if r.get("destiny_number"):
        lines.append(f"   Destiny Number: {r['destiny_number']}")
    lines.append("")

    lucky_nums = r.get("lucky_numbers") or []
    if lucky_nums:
        lines.append("🍀 Lucky numbers: " + ", ".join(str(n) for n in lucky_nums))
    if r.get("today_vibe_number"):
        lines.append(f"   Today's vibe: {r['today_vibe_number']}")
    lines.append("")

    colors = r.get("lucky_colors") or []
    if colors:
        lines.append("🎨 Lucky colors:")
        for c in colors:
            name = c.get("name", "") if isinstance(c, dict) else getattr(c, "name", "")
            reason = c.get("reason", "") if isinstance(c, dict) else getattr(c, "reason", "")
            lines.append(f"   · {name} — {reason}")
        lines.append("")

    days = r.get("lucky_days") or []
    if days:
        lines.append("📅 Lucky days:")
        for d in days:
            day = d.get("day", "") if isinstance(d, dict) else getattr(d, "day", "")
            reason = d.get("reason", "") if isinstance(d, dict) else getattr(d, "reason", "")
            lines.append(f"   · {day} — {reason}")
        lines.append("")

    stone = r.get("lucky_stone")
    if stone:
        name = stone.get("name", "") if isinstance(stone, dict) else getattr(stone, "name", "")
        expl = stone.get("explanation", "") if isinstance(stone, dict) else getattr(stone, "explanation", "")
        lines.append(f"💎 Lucky stone: {name}")
        lines.append(f"   {expl}")
        lines.append("")

    if r.get("power_phrase"):
        lines.append(f"🌟 Your power phrase: \"{r['power_phrase']}\"")
        lines.append("")
    if r.get("quick_tip"):
        lines.append(f"✨ Quick tip: {r['quick_tip']}")
        lines.append("")
    if r.get("follow_up_question"):
        lines.append(f"🔮 {r['follow_up_question']}")

    return "\n".join(lines).strip()


def _extract_json_from_response(text: str) -> dict | None:
    """Parse JSON from LLM response, stripping markdown code blocks if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ────────────────────────────────────────────────
#   Caller function
# ────────────────────────────────────────────────


async def call_numerology_agent(profile: dict) -> dict:
    """
    Run numerology reading from profile (dob required; name, place optional).
    Returns {"data": <NumerologyReading dict>, "message": <formatted str>} on success,
    or {"message": <error str>} on failure. Do not store when only "message" is returned.
    """
    dob_raw = profile.get("dob") if isinstance(profile, dict) else None
    name = profile.get("name") if isinstance(profile, dict) else None
    place = profile.get("place") if isinstance(profile, dict) else None

    if not dob_raw:
        return {"message": "Hey, I need your full birth date to vibe with your numbers! 🌟 What's your DOB?"}

    parsed = parse_dob_from_profile(str(dob_raw))
    if not parsed:
        return {"message": "I couldn't read that date. Please use DD-MM-YYYY or tell me your full birth date! 🌟"}

    day, month, year = parsed
    dob_str = f"{day:02d}-{month:02d}-{year}"

    # Calculate numbers
    mulank = calculate_mulank(day)
    if mulank == -1:
        return {"message": "Oops, invalid day in birth date. Let's try again! 🔮"}

    life_path = calculate_life_path_number(dob_str)
    mulank_traits = get_number_traits(mulank)
    life_path_traits = get_number_traits(life_path)
    destiny_number = None
    destiny_traits = None
    destiny_info = ""
    if name:
        destiny_number = calculate_destiny_number(name)
        destiny_traits = get_number_traits(destiny_number)
        destiny_info = f"Destiny Number: {destiny_number} - traits: {destiny_traits}"

    calculated_from = CalculatedFrom(dob=dob_str, name_used=bool(name), place_used=bool(place))

    # One LLM call for structured JSON
    response = llm.complete(
        STRUCTURED_GENERATION_PROMPT.format(
            mulank=mulank,
            mulank_traits=mulank_traits,
            life_path=life_path,
            life_path_traits=life_path_traits,
            destiny_info=destiny_info,
        )
    )
    raw_str = response.text.strip()
    logger.info(f"Raw string: {raw_str}")
    llm_json = _extract_json_from_response(raw_str)


    if not llm_json:
        # Retry once
        response = llm.complete(
            STRUCTURED_GENERATION_PROMPT.format(
                mulank=mulank,
                mulank_traits=mulank_traits,
                life_path=life_path,
                life_path_traits=life_path_traits,
                destiny_info=destiny_info,
            )
        )
        llm_json = _extract_json_from_response(response.text.strip())

    if not llm_json:
        return {"message": "Sorry, something went wrong generating your reading. Please try again! 🌟"}

    # Merge calculated + generated and validate
    payload: dict[str, Any] = {
        "life_path_number": life_path,
        "mulank": mulank,
        "destiny_number": destiny_number,
        "life_path_traits": life_path_traits,
        "mulank_traits": mulank_traits,
        "destiny_traits": destiny_traits,
        "calculated_from": calculated_from.model_dump(),
        "lucky_numbers": llm_json.get("lucky_numbers", []),
        "today_vibe_number": llm_json.get("today_vibe_number"),
        "lucky_colors": [c if isinstance(c, dict) else {"name": getattr(c, "name", ""), "reason": getattr(c, "reason", "")} for c in (llm_json.get("lucky_colors") or [])],
        "lucky_days": [d if isinstance(d, dict) else {"day": getattr(d, "day", ""), "reason": getattr(d, "reason", "")} for d in (llm_json.get("lucky_days") or [])],
        "lucky_stone": llm_json.get("lucky_stone"),
        "power_phrase": llm_json.get("power_phrase", ""),
        "quick_tip": llm_json.get("quick_tip", ""),
        "follow_up_question": llm_json.get("follow_up_question", ""),
        "personality_summary": llm_json.get("personality_summary"),
        "main_challenge": llm_json.get("main_challenge"),
        "suggested_follow_ups": llm_json.get("suggested_follow_ups", []),
    }
    stone = payload.get("lucky_stone")
    if stone and isinstance(stone, dict) and stone.get("name") and stone.get("explanation"):
        payload["lucky_stone"] = {"name": stone["name"], "explanation": stone["explanation"]}
    elif stone and not isinstance(stone, dict):
        payload["lucky_stone"] = {"name": getattr(stone, "name", ""), "explanation": getattr(stone, "explanation", "")} if (getattr(stone, "name", None) and getattr(stone, "explanation", None)) else None
    else:
        payload["lucky_stone"] = None

    try:
        reading = NumerologyReading.model_validate(payload)
        logger.info(f"Numerology reading: {payload}")
    except Exception:
        return {"message": "Sorry, something went wrong generating your reading. Please try again! 🌟"}

    message = format_numerology_message(reading)
    data = reading.model_dump(mode="json")
    return {"data": data, "message": message}