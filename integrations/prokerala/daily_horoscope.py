"""
Prokerala v2 daily horoscope: get_daily_horoscope(sign, date).
Uses advanced endpoint for General, Career, Love, Health.
"""
import json
from datetime import date, datetime
from typing import Any

import urllib.parse
import urllib.request

from integrations.prokerala.auth import get_access_token  # noqa: I001 (run from astro_genie as cwd)

BASE_URL = "https://api.prokerala.com/v2"
VALID_SIGNS = {
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
}


def get_daily_horoscope(sign: str, dt: date | None = None) -> dict[str, Any]:
    """
    Fetch daily horoscope for the given zodiac sign.
    :param sign: lowercase sign name (e.g. aries, virgo).
    :param dt: date for prediction; default today.
    :return: raw API response dict (status, data with daily_predictions or error).
    """
    sign = (sign or "").strip().lower()
    if sign not in VALID_SIGNS:
        return {"status": "error", "message": f"Invalid sign: {sign}"}

    target = dt or date.today()
    # API expects ISO 8601 datetime; use noon UTC for the day
    datetime_str = datetime(target.year, target.month, target.day, 12, 0, 0).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    datetime_encoded = urllib.parse.quote(datetime_str, safe="")

    path = f"/horoscope/daily/advanced?datetime={datetime_encoded}&sign={sign}&type=all"
    url = BASE_URL + path
    token = get_access_token()
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            return {"status": "error", "message": err.get("message", body) or str(e)}
        except Exception:
            return {"status": "error", "message": body or str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
