"""
Agent that answers follow-up questions using the user's stored persona (astro_data).
Use when the user already has a reading and returns to ask more.
"""

import json
import re
from services.llm_service import call_llm


def _persona_context(persona: dict) -> str:
    """Build a short, readable context string from persona for the LLM."""
    parts = []
    if not persona:
        return "No stored context."

    num = persona.get("numerology")
    if num:
        parts.append("Numerology reading:")
        parts.append(f"  Life Path: {num.get('life_path_number')} ({num.get('life_path_traits', '')})")
        parts.append(f"  Mulank: {num.get('mulank')} ({num.get('mulank_traits', '')})")
        if num.get("destiny_number"):
            parts.append(f"  Destiny Number: {num.get('destiny_number')} ({num.get('destiny_traits', '')})")
        if num.get("lucky_numbers"):
            parts.append(f"  Lucky numbers: {num.get('lucky_numbers')}")
        if num.get("power_phrase"):
            parts.append(f"  Power phrase: {num.get('power_phrase')}")
        if num.get("lucky_colors"):
            colors = [c.get("name", "") for c in (num.get("lucky_colors") or []) if isinstance(c, dict)]
            if colors:
                parts.append(f"  Lucky colors: {', '.join(colors)}")
        if num.get("lucky_stone") and isinstance(num.get("lucky_stone"), dict):
            parts.append(f"  Lucky stone: {num['lucky_stone'].get('name', '')} — {num['lucky_stone'].get('explanation', '')}")
        if num.get("personality_summary"):
            parts.append(f"  Personality: {num.get('personality_summary')}")
        if num.get("quick_tip"):
            parts.append(f"  Quick tip: {num.get('quick_tip')}")
        parts.append("")

    astro = persona.get("astrology")
    if astro and isinstance(astro, dict):
        parts.append("Astrology context:")
        parts.append(json.dumps(astro, default=str)[:500])
        parts.append("")

    return "\n".join(parts).strip() if parts else "No stored context."


FOLLOW_UP_PROMPT = """You are Astro Genie 🔮 — a warm, supportive astrology and numerology guide. The user has already received their reading and is back with a follow-up question. Use their stored context below to give a personalized, relevant answer. Keep replies concise (2–4 short paragraphs max), friendly, and slightly mystical. Use a few emojis if it fits. Don't repeat their full reading; refer to it only where it helps answer their question.

Stored context for this user:
{context}

User's question: {question}

Answer as their personal guide:"""

TOPIC_HINTS: dict[str, tuple[tuple[str, ...], str]] = {
    "career": (
        ("1", "career", "job", "work", "money", "finance", "salary", "business"),
        "Please focus on career and money guidance for me based on my stored numerology profile. Keep it practical and concise.",
    ),
    "relationship": (
        ("2", "love", "relationship", "partner", "marriage", "romance", "dating"),
        "Please focus on love and relationship guidance for me based on my stored numerology profile. Keep it warm and concise.",
    ),
    "life_purpose": (
        ("3", "purpose", "calling", "mission", "direction", "life goal", "path"),
        "Please focus on life purpose guidance for me based on my stored numerology profile. Keep it clear and actionable.",
    ),
    "daily_horoscope": (
        ("4", "today horoscope", "daily horoscope", "daily prediction", "today's horoscope"),
        "",
    ),
}


class FollowUpAgent:
    """Answers user questions using stored persona (numerology/astrology) from astro_data."""

    @staticmethod
    def map_topic_message(message: str) -> tuple[str | None, str | None]:
        """
        Lightweight mapper for numeric or free-text topic picks.
        Returns (topic_key, rewritten_prompt). Topic 4 is routed in orchestrator.
        """
        text = str(message or "").strip().lower()
        if not text:
            return None, None
        compact = re.sub(r"\s+", " ", text)
        for topic, (terms, prompt) in TOPIC_HINTS.items():
            if compact == terms[0]:
                return topic, prompt
            if any(term in compact for term in terms[1:]):
                return topic, prompt
        return None, None

    def answer(self, phone: str, message: str, persona: dict) -> str:
        """
        Generate a personalized reply using the user's persona and their message.
        :param phone: user phone (for logging/future use)
        :param message: user's follow-up question or message
        :param persona: dict from get_persona(phone), e.g. {"numerology": {...}, "astrology": {...}}
        :return: reply string to send to the user
        """
        context = _persona_context(persona or {})
        _, mapped_prompt = self.map_topic_message(message)
        question = mapped_prompt or message.strip()
        prompt = FOLLOW_UP_PROMPT.format(context=context, question=question)
        return call_llm(prompt)
