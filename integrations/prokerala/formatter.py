"""
Format Prokerala daily horoscope API response into a short readable message (Love, Career, Health, General).
"""
from typing import Any


def format_daily_horoscope_response(data: dict[str, Any]) -> str:
    """
    Turn API response (advanced daily) into 2–4 short paragraphs or bullet lines.
    :param data: raw get_daily_horoscope response (status, data with daily_predictions).
    :return: formatted string for WhatsApp/user.
    """
    if data.get("status") != "ok":
        return data.get("message", "Could not fetch your daily horoscope. Please try again later.")

    payload = data.get("data") or {}
    predictions_list = payload.get("daily_predictions") or []
    if not predictions_list:
        return "No predictions available for today."

    # Take first sign's predictions (we requested one sign)
    block = predictions_list[0]
    predictions = block.get("predictions") or []
    sign_name = (block.get("sign") or {}).get("name", "").strip() or "Your sign"

    parts = [f"✨ Daily horoscope for {sign_name} ✨", ""]
    for p in predictions:
        ptype = (p.get("type") or "").strip()
        text = (p.get("prediction") or "").strip()
        if not text:
            continue
        if ptype:
            parts.append(f"{ptype}:")
        # Keep first 2–3 sentences for WhatsApp
        sentences = text.replace("..", ".").split(".")
        short = ". ".join(s for s in sentences[:3] if s.strip()).strip()
        if short:
            parts.append(short)
            if not short.endswith("."):
                parts[-1] += "."
        parts.append("")

    return "\n".join(parts).strip() or "No predictions available for today."
