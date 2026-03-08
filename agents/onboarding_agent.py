"""
Onboarding agent responsible for collecting core profile fields:
- dob (date of birth)
- tob (time of birth)
- pob (place of birth, enriched with geo fields)
- name
"""
from __future__ import annotations

import re
from datetime import datetime
import logging

from services.location_service import enrich_place

logger = logging.getLogger(__name__)

ENTRY_MSG = """✨ Hi, I’m Astro Genie 🔮
I help you understand your life through astrology & numerology.
Let’s begin 🌙 What is your Date of Birth? (DD-MM-YYYY)"""


class OnboardingAgent:
    def __init__(self, mongo):
        self.mongo = mongo

    @staticmethod
    def _parse_dob(raw: str) -> str | None:
        text = (raw or "").strip()
        if not text:
            return None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                dt = datetime.strptime(text, fmt)
                if dt.year < 1900 or dt.year > 2100:
                    return None
                return dt.strftime("%d-%m-%Y")
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_tob(raw: str) -> str | None:
        text = (raw or "").strip()
        if not text:
            return None
        if text.lower() == "unknown":
            return "12:00"
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
            try:
                return datetime.strptime(text, fmt).strftime("%H:%M")
            except ValueError:
                continue
        return None

    @staticmethod
    def _clean_name(raw: str) -> str | None:
        text = re.sub(r"\s+", " ", (raw or "").strip())
        if len(text) < 2:
            return None
        if not re.search(r"[A-Za-z]", text):
            return None
        return text

    def _reconcile_state_from_profile(self, phone: str, state: str) -> str:
        """
        Keep onboarding state consistent with stored profile fields.
        This prevents dead loops when state says PROFILE_READY but data is incomplete.
        """
        profile = self.mongo.get_profile(phone) or {}
        has_dob = bool(self._parse_dob(str(profile.get("dob") or "")))
        has_tob = bool(self._parse_tob(str(profile.get("tob") or "")))
        has_pob_text = bool(str(profile.get("pob") or "").strip())
        has_pob_geo = bool(str(profile.get("pob_lat") or "").strip()) and bool(str(profile.get("pob_lon") or "").strip())
        has_pob = has_pob_text and has_pob_geo
        has_name = bool(self._clean_name(str(profile.get("name") or "")))

        if not has_dob:
            target = "ASK_DOB"
        elif not has_tob:
            target = "ASK_TOB"
        elif not has_pob:
            target = "ASK_POB"
        elif not has_name:
            target = "ASK_NAME"
        else:
            target = "PROFILE_READY"

        known_states = {"NEW_USER", "ASK_DOB", "ASK_TOB", "ASK_POB", "ASK_NAME", "PROFILE_READY"}
        current = state if state in known_states else "NEW_USER"

        # NEW_USER with partial profile should continue from missing field, not restart blindly.
        if current == "NEW_USER" and target != "ASK_DOB":
            self.mongo.update_state(phone, target)
            logger.info("Onboarding state repaired phone=%s from=%s to=%s", phone, current, target)
            return target

        # PROFILE_READY with missing data should be repaired.
        if current == "PROFILE_READY" and target != "PROFILE_READY":
            self.mongo.update_state(phone, target)
            logger.info("Onboarding state repaired phone=%s from=%s to=%s", phone, current, target)
            return target

        # Unknown state fallback.
        if state not in known_states:
            self.mongo.update_state(phone, "NEW_USER")
            logger.info("Onboarding unknown state reset phone=%s old=%s new=NEW_USER", phone, state)
            return "NEW_USER"

        return current

    def handle(self, phone: str, message: str) -> str | None:
        raw_state = self.mongo.get_state(phone)
        state = self._reconcile_state_from_profile(phone, raw_state)

        if state == "NEW_USER":
            self.mongo.update_state(phone, "ASK_DOB")
            return ENTRY_MSG

        if state == "ASK_DOB":
            dob = self._parse_dob(message)
            if not dob:
                return "Please enter DOB in DD-MM-YYYY format 😊"
            self.mongo.save_profile_field(phone, "dob", dob)
            self.mongo.update_state(phone, "ASK_TOB")
            return "Thank you ✨ What is your Time of Birth? (or type Unknown)"

        if state == "ASK_TOB":
            tob = self._parse_tob(message)
            if not tob:
                return "Please enter Time of Birth in HH:MM (24h) format, or type Unknown 😊"
            self.mongo.save_profile_field(phone, "tob", tob)
            self.mongo.update_state(phone, "ASK_POB")
            return "Got it 🌍 Please tell me your Place of Birth (City, Country)"

        if state == "ASK_POB":
            place_raw = (message or "").strip()
            if len(place_raw) < 2:
                return "Please share your Place of Birth clearly (for example: Kolkata, India) 😊"

            geo = enrich_place(place_raw)
            if geo.get("status") == "ok":
                normalized_place = str(geo.get("normalized_place") or place_raw)
                self.mongo.save_profile_field(phone, "pob", normalized_place)
                if geo.get("city"):
                    self.mongo.save_profile_field(phone, "pob_city", str(geo.get("city")))
                if geo.get("state"):
                    self.mongo.save_profile_field(phone, "pob_state", str(geo.get("state")))
                if geo.get("country"):
                    self.mongo.save_profile_field(phone, "pob_country", str(geo.get("country")))
                if geo.get("latitude") is not None:
                    self.mongo.save_profile_field(phone, "pob_lat", str(geo.get("latitude")))
                if geo.get("longitude") is not None:
                    self.mongo.save_profile_field(phone, "pob_lon", str(geo.get("longitude")))
                if geo.get("timezone"):
                    self.mongo.save_profile_field(phone, "pob_timezone", str(geo.get("timezone")))
                if geo.get("source"):
                    self.mongo.save_profile_field(phone, "pob_geo_source", str(geo.get("source")))
            else:
                logger.warning("POB enrich failed phone=%s place=%r err=%s", phone, place_raw, geo.get("message"))
                return (
                    "I couldn't verify that location yet 🌍\n"
                    "Please send your Place of Birth as: City, Country\n"
                    "Example: Bidar, India"
                )

            self.mongo.update_state(phone, "ASK_NAME")
            return "Almost done ✨ What is your Full Name?"

        if state == "ASK_NAME":
            name = self._clean_name(message)
            if not name:
                return "Please share your full name so I can personalize your reading 😊"
            self.mongo.save_profile_field(phone, "name", name)
            self.mongo.update_state(phone, "PROFILE_READY")
            return "🔮 Thank you! Preparing your reading..."

        return None
