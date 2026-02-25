"""
Map DOB to western sun sign for Prokerala daily horoscope.
Supports DD-MM-YYYY and YYYY-MM-DD (reuses logic similar to numerology_agent.parse_dob_from_profile).
"""
import re

# Tropical sun sign boundaries: (month, day) on or before which the sign ends.
# Each entry: (month, last_day_of_previous_sign) -> sign name (lowercase).
# Capricorn starts Dec 22, so "previous" sign Sagittarius ends Dec 21, etc.
_SIGN_BOUNDARIES = [
    (1, 19, "capricorn"),   # Jan 1-19
    (2, 18, "aquarius"),    # Jan 20 - Feb 18
    (3, 20, "pisces"),      # Feb 19 - Mar 20
    (4, 19, "aries"),      # Mar 21 - Apr 19
    (5, 20, "taurus"),     # Apr 20 - May 20
    (6, 20, "gemini"),     # May 21 - Jun 20
    (7, 22, "cancer"),     # Jun 21 - Jul 22
    (8, 22, "leo"),        # Jul 23 - Aug 22
    (9, 22, "virgo"),      # Aug 23 - Sep 22
    (10, 22, "libra"),     # Sep 23 - Oct 22
    (11, 21, "scorpio"),   # Oct 23 - Nov 21
    (12, 21, "sagittarius"),  # Nov 22 - Dec 21
    (12, 31, "capricorn"),   # Dec 22-31
]


def _parse_dob(dob_str: str) -> tuple[int, int, int] | None:
    """Parse DOB to (day, month, year). Supports DD-MM-YYYY and YYYY-MM-DD."""
    if not dob_str or not isinstance(dob_str, str):
        return None
    digits = re.findall(r"\d+", dob_str)
    if len(digits) < 3:
        return None
    d, m, y = int(digits[0]), int(digits[1]), int(digits[2])
    if 1 <= d <= 31 and 1 <= m <= 12 and 1900 < y < 2100:
        return (d, m, y)
    if 1900 <= d <= 2100 and 1 <= m <= 12 and 1 <= y <= 31:
        return (y, m, d)  # YYYY-MM-DD -> (day, month, year)
    return None


def dob_to_sun_sign(dob_str: str) -> str | None:
    """
    Map date of birth to western sun sign (lowercase) for API.
    :param dob_str: DOB string (DD-MM-YYYY or YYYY-MM-DD).
    :return: lowercase sign name (e.g. aries, virgo) or None if unparseable.
    """
    parsed = _parse_dob(dob_str)
    if not parsed:
        return None
    day, month, _ = parsed
    for end_month, end_day, sign in _SIGN_BOUNDARIES:
        if (month, day) <= (end_month, end_day):
            return sign
    return "capricorn"
