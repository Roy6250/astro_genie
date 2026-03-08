"""
Transform Prokerala horoscope API output into short, high-retention AstroGenie guidance.
Flow:
raw API -> structured fields -> LLM polish -> WhatsApp-ready micro experience
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from utils.custom_llm import OurLLM

logger = logging.getLogger(__name__)

_llm = OurLLM()

_TYPE_ALIASES: dict[str, str] = {
    "general": "general",
    "overview": "general",
    "career": "career",
    "profession": "career",
    "business": "career",
    "love": "love",
    "relationship": "love",
    "romance": "love",
    "health": "health",
    "wellness": "health",
}

_POWER_WORDS = [
    "Clarity",
    "Discipline",
    "Balance",
    "Momentum",
    "Patience",
    "Focus",
    "Trust",
    "Stability",
    "Courage",
    "Harmony",
    "Presence",
    "Intent",
]

_PLANET_PATTERN = re.compile(
    r"\b(Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Rahu|Ketu)\b[^.]{0,80}",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    return cleaned.strip(" -")


def _first_sentence(text: str, max_sentences: int = 1) -> str:
    if not text:
        return ""
    pieces = re.split(r"(?<=[.!?])\s+", _clean_text(text))
    chosen = " ".join(p.strip() for p in pieces[:max_sentences] if p.strip())
    return chosen.rstrip(".!?")


def _de_genericize_sentence(text: str, sign: str) -> str:
    if not text:
        return ""
    out = _clean_text(text)
    sign_plural = f"{sign}s"
    patterns = [
        rf"^today,\s*{re.escape(sign_plural)}\s*,?\s*may\s+find\s+themselves\s+",
        rf"^today\s+{re.escape(sign_plural)}\s*,?\s*may\s+find\s+themselves\s+",
        rf"^today,\s*{re.escape(sign)}\s*,?\s*",
        rf"^today\s+{re.escape(sign)}\s*,?\s*",
    ]
    for pat in patterns:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    return out[:1].upper() + out[1:] if out else out


def _pick_power_word(sign_name: str, dt: str) -> str:
    seed = f"{sign_name.lower()}|{dt}"
    idx = sum(ord(ch) for ch in seed) % len(_POWER_WORDS)
    return _POWER_WORDS[idx]


def _extract_structured_horoscope(data: dict[str, Any]) -> dict[str, Any] | None:
    payload = data.get("data") or {}
    predictions_list = payload.get("daily_predictions") or []
    if not predictions_list:
        return None

    block = predictions_list[0] or {}
    sign_name = _clean_text(((block.get("sign") or {}).get("name") or "Your sign"))
    dt = str(block.get("date") or date.today().isoformat())[:10]
    predictions = block.get("predictions") or []

    sections = {"general": "", "career": "", "love": "", "health": ""}
    planetary_aspects: list[str] = []

    for pred in predictions:
        ptype = _clean_text(str(pred.get("type") or "")).lower()
        text = _clean_text(str(pred.get("prediction") or ""))
        if not text:
            continue

        mapped = _TYPE_ALIASES.get(ptype)
        if mapped and not sections[mapped]:
            sections[mapped] = _first_sentence(text, max_sentences=2)

        for match in _PLANET_PATTERN.findall(text):
            candidate = match.strip().title()
            if candidate and candidate not in planetary_aspects:
                planetary_aspects.append(candidate)

    # Fill missing sections with short snippets from any available prediction.
    if predictions:
        fallback_snippets = [
            _first_sentence(_clean_text(str(item.get("prediction") or "")), max_sentences=1)
            for item in predictions
            if _clean_text(str(item.get("prediction") or ""))
        ]
        fallback_snippets = [s for s in fallback_snippets if s]
        for key in sections:
            if not sections[key] and fallback_snippets:
                sections[key] = fallback_snippets.pop(0)

    return {
        "sign": sign_name or "Your sign",
        "date": dt,
        "general": sections["general"],
        "career": sections["career"],
        "love": sections["love"],
        "health": sections["health"],
        "planetary_aspects": planetary_aspects[:5],
    }


def _extract_personal_lens(persona_context: dict[str, Any] | None) -> str:
    if not isinstance(persona_context, dict):
        return ""
    numerology = persona_context.get("numerology")
    astrology = persona_context.get("astrology")

    if isinstance(numerology, dict):
        life_path = numerology.get("life_path_number")
        mulank = numerology.get("mulank")
        personality = _clean_text(str(numerology.get("personality_summary") or ""))
        challenge = _clean_text(str(numerology.get("main_challenge") or ""))
        if isinstance(life_path, int):
            if challenge:
                return f"Your Life Path {life_path} favors consistency today, especially if you avoid {challenge.lower()}."
            return f"Your Life Path {life_path} favors steady progress over dramatic moves."
        if isinstance(mulank, int):
            return f"Your Mulank {mulank} suggests simple, focused action works best today."
        if personality:
            return f"Personal lens: {personality[:90]}."

    if isinstance(astrology, dict):
        personality = _clean_text(str(astrology.get("personality") or ""))
        challenge = _clean_text(str(astrology.get("challenge") or ""))
        if personality and challenge:
            return f"Personal lens: your {personality} side is strong today; watch {challenge.lower()}."
        if personality:
            return f"Personal lens: lean into your {personality} side today."

    return ""


def _strip_code_fences(text: str) -> str:
    txt = (text or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", txt).strip()
        txt = re.sub(r"\n?```$", "", txt).strip()
    return txt


def _build_polish_prompt(
    structured: dict[str, Any],
    power_word: str,
    user_name: str | None = None,
    personal_lens: str = "",
) -> str:
    lines = [
        "You are AstroGenie, a calm daily mentor.",
        "Rewrite the horoscope data into a WhatsApp-ready micro guidance message.",
        "Rules:",
        "- Max 180 words",
        "- 7 to 10 short lines",
        "- Warm, direct, emotionally intelligent tone",
        "- No fear-based language",
        "- Speak directly to the user as their sign (for example: 'Libra, ...')",
    ]
    if user_name:
        lines.append(f"- Use the user's name naturally once: {user_name}")
    lines.extend(
        [
            "- Keep this exact top line format: ✨ AstroGenie Daily - <Sign>",
            f"- Include this exact line: 🔑 Power Word: {power_word}",
            "- Include a one-line 'today energy' insight",
            "- Include concise lines for career, love, and health",
            "- Include one 'Genie Tip' actionable line",
        ]
    )
    if personal_lens:
        lines.append(
            "- Include one short line called '🧬 Personal Lens' that uses this context: "
            + personal_lens
        )
    lines.extend(
        [
            "- End with one curiosity hook: 'This is general <Sign> energy. Your personal chart may shift this.'",
            "- Avoid repetitive boilerplate phrases",
            "",
            "Structured data JSON:",
            json.dumps(structured, ensure_ascii=True),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _fallback_message(
    structured: dict[str, Any],
    power_word: str,
    user_name: str | None = None,
    personal_lens: str = "",
) -> str:
    sign = structured.get("sign", "Your sign")
    general = _de_genericize_sentence(
        structured.get("general") or "Today feels steady with a hint of surprise.",
        sign,
    )
    career = _de_genericize_sentence(
        structured.get("career") or "Move one idea forward, but keep scope tight.",
        sign,
    )
    love = _de_genericize_sentence(
        structured.get("love") or "Choose consistency over overthinking.",
        sign,
    )
    health = _de_genericize_sentence(
        structured.get("health") or "Keep your routine light and repeatable.",
        sign,
    )
    address = f"{user_name}, " if user_name else f"{sign}, "
    lens_line = f"🧬 Personal Lens: {personal_lens}\n" if personal_lens else ""

    return (
        f"✨ AstroGenie Daily - {sign}\n"
        f"🔑 Power Word: {power_word}\n"
        f"🌤 {address}{general}\n"
        f"🎯 Focus: Keep structure, but leave room for one unexpected shift.\n"
        f"💼 Career: {_first_sentence(career, max_sentences=1)}.\n"
        f"❤️ Love: {_first_sentence(love, max_sentences=1)}.\n"
        f"🌿 Health: {_first_sentence(health, max_sentences=1)}.\n"
        f"{lens_line}"
        "🧿 Genie Tip: Organize one small task you've been postponing.\n"
        f"This is general {sign} energy. Your personal chart may shift this."
    )


def _enforce_length(message: str, max_words: int = 180) -> str:
    words = message.split()
    if len(words) <= max_words:
        return message.strip()
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:")
    if not trimmed.endswith("."):
        trimmed += "."
    return trimmed


def _postprocess_polished_message(message: str, sign: str, user_name: str | None = None) -> str:
    lines = [ln.strip() for ln in (message or "").splitlines() if ln.strip()]
    cleaned_lines: list[str] = []
    sign_plural = f"{sign}s"
    for ln in lines:
        out = ln
        out = re.sub(
            rf":\s*Today,\s*{re.escape(sign)}\s*,?\s*",
            ": ",
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(
            rf"(\s|^)(Today,\s*{re.escape(sign_plural)}\s+may\s+find\s+themselves\s+)",
            " ",
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(
            rf"(\s|^)(Today,\s*{re.escape(sign)}\s*,?\s*)",
            " ",
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(r"\s{2,}", " ", out).strip()
        cleaned_lines.append(out)

    if user_name:
        has_name = any(user_name.lower() in ln.lower() for ln in cleaned_lines)
        if not has_name:
            for i, ln in enumerate(cleaned_lines):
                if ln.startswith("🌤"):
                    body = ln[1:].strip()
                    cleaned_lines[i] = f"🌤 {user_name}, {body}".replace(f"{user_name}, {user_name},", f"{user_name},")
                    break

    return "\n".join(cleaned_lines).strip()


def _ensure_required_lines(
    message: str,
    sign: str,
    power_word: str,
    fallback: str,
    user_name: str | None = None,
) -> str:
    txt = message.strip()
    if not txt:
        return fallback
    lower = txt.lower()
    required_checks = [
        "astrogenie daily",
        "power word",
        "career",
        "love",
        "health",
        "genie tip",
    ]
    if not all(token in lower for token in required_checks):
        return fallback
    if f"general {sign.lower()} energy" not in lower:
        txt = txt.rstrip() + f"\nThis is general {sign} energy. Your personal chart may shift this."
    if "🔑 power word" not in lower:
        txt = f"✨ AstroGenie Daily - {sign}\n🔑 Power Word: {power_word}\n" + txt
    if user_name and user_name.lower() not in txt.lower():
        txt_lines = txt.splitlines()
        for idx, line in enumerate(txt_lines):
            if line.startswith("🌤"):
                txt_lines[idx] = f"🌤 {user_name}, {line[1:].strip()}"
                break
        txt = "\n".join(txt_lines)
    return txt


def format_daily_horoscope_response(data: dict[str, Any]) -> str:
    """
    Convert Prokerala advanced horoscope payload into concise AstroGenie daily guidance.
    """
    return format_daily_horoscope_response_with_context(data)


def format_daily_horoscope_response_with_context(
    data: dict[str, Any],
    user_name: str | None = None,
    persona_context: dict[str, Any] | None = None,
) -> str:
    """
    Personalized formatter:
    - Uses Prokerala daily data as base
    - Adds user name and persona cues (if available) for a personal touch
    """
    if data.get("status") != "ok":
        return data.get("message", "Could not fetch your daily horoscope. Please try again later.")

    structured = _extract_structured_horoscope(data)
    if not structured:
        return "No predictions available for today."

    user_name = _clean_text(user_name or "")
    if not user_name:
        user_name = None
    personal_lens = _extract_personal_lens(persona_context)

    sign = structured["sign"]
    power_word = _pick_power_word(sign, structured["date"])
    fallback = _fallback_message(structured, power_word, user_name=user_name, personal_lens=personal_lens)

    prompt = _build_polish_prompt(
        structured,
        power_word,
        user_name=user_name,
        personal_lens=personal_lens,
    )
    try:
        response = _llm.complete(prompt, temperature=0.55, max_tokens=320)
        polished = _strip_code_fences(getattr(response, "text", "") or "")
        polished = _postprocess_polished_message(polished, sign, user_name=user_name)
        polished = _ensure_required_lines(
            polished,
            sign,
            power_word,
            fallback,
            user_name=user_name,
        )
        polished = _enforce_length(polished, max_words=180)
        return polished
    except Exception as exc:
        logger.warning("Failed to run AstroGenie polish layer; using fallback. err=%s", exc)
        return fallback
