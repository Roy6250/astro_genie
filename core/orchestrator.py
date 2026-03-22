import asyncio
from datetime import date
from datetime import datetime
from uuid import uuid4

from config import MCP_SERVER_URL
from core.state_machine import StateMachine
from memory.mongo_manager import MongoManager
from memory.memory_service import MemoryService
from agents.astrology_agent import AstrologyAgent
from agents.numerology_agent import call_numerology_agent
from agents.interpretation_agent import InterpretationAgent
from agents.formatter_agent import FormatterAgent
from agents.follow_up_agent import FollowUpAgent
from agents.intent_agent import classify as classify_intent
from services.whatsapp_service import send_whatsapp_message
from utils.zodiac import dob_to_sun_sign
from mcp_serv.client import call_tool as mcp_call_tool
import logging
logger = logging.getLogger(__name__)

class Orchestrator:

    def __init__(self):
        self.fsm = StateMachine()
        self.mongo = MongoManager()
        self.memory = MemoryService(self.mongo)
        self.astro = AstrologyAgent()
        self.interpreter = InterpretationAgent()
        self.formatter = FormatterAgent()
        self.follow_up = FollowUpAgent()

    @staticmethod
    def _build_daily_persona_context(persona: dict | None) -> dict | None:
        """
        Keep only compact, high-signal persona fields for daily personalization.
        """
        if not isinstance(persona, dict):
            return None

        out: dict[str, dict] = {}

        num = persona.get("numerology")
        if isinstance(num, dict):
            num_ctx = {
                "life_path_number": num.get("life_path_number"),
                "mulank": num.get("mulank"),
                "personality_summary": num.get("personality_summary"),
                "main_challenge": num.get("main_challenge"),
            }
            num_ctx = {k: v for k, v in num_ctx.items() if v not in (None, "", [], {})}
            if num_ctx:
                out["numerology"] = num_ctx

        astro = persona.get("astrology")
        if isinstance(astro, dict):
            astro_ctx = {
                "personality": astro.get("personality"),
                "challenge": astro.get("challenge"),
            }
            astro_ctx = {k: v for k, v in astro_ctx.items() if v not in (None, "", [], {})}
            if astro_ctx:
                out["astrology"] = astro_ctx

        return out or None

    @staticmethod
    def _should_send_welcome_back(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        return text in {
            "hi",
            "hello",
            "hey",
            "hii",
            "yo",
            "start",
            "menu",
            "continue",
            "continue reading",
            "welcome back",
        }

    @staticmethod
    def _build_welcome_back_prompt(returning_ctx: dict) -> str:
        name = str(returning_ctx.get("display_name") or "").strip()
        life_path = returning_ctx.get("life_path")
        greet_name = f" {name.split()[0]}" if name else ""
        life_path_line = f" Your Life Path {life_path} energy is still guiding this phase." if life_path else ""
        return (
            f"✨ Welcome back{greet_name}!{life_path_line}\n"
            "Pick a focus or ask anything naturally:\n"
            "1) Career & money\n"
            "2) Love & relationships\n"
            "3) Life purpose\n"
            "4) Today's horoscope"
        )

    @staticmethod
    def _build_curiosity_followup(reading: dict) -> str | None:
        if not isinstance(reading, dict):
            return None
        life_path = reading.get("life_path_number")
        mulank = reading.get("mulank")
        if not life_path and not mulank:
            return None
        lp_part = f"Life Path {life_path}" if life_path else "your core energy"
        mk_part = f" + Mulank {mulank}" if mulank else ""
        return (
            f"🔮 Quick insight: With {lp_part}{mk_part}, your next 7 days look like a decision cycle."
            " Want me to decode whether this window favors career, love, or timing?"
        )

    async def handle_message(self, phone, message):
        query_id = uuid4().hex[:10]
        logger.info("QUERY_START id=%s phone=%s text=%r", query_id, phone, message)
        self.memory.store_short(phone, "user", str(message or ""))
        self.memory.maybe_store_long(phone, "user", str(message or ""))

        self._log_tool_call(phone, query_id, "onboarding_agent.handle")
        fsm_reply = self.fsm.handle(phone, message)
        if fsm_reply:
            logger.info("Onboarding response generated phone=%s text=%r", phone, fsm_reply)
            self._send_reply(phone, fsm_reply)
            # If onboarding just completed, continue in same turn and hand over to numerology.
            if self.mongo.get_state(phone) != "PROFILE_READY":
                logger.info("QUERY_END id=%s phone=%s handled_by=onboarding", query_id, phone)
                return
            logger.info("Onboarding completed for phone=%s; handing over to numerology", phone)

        profile = self.mongo.get_profile(phone)
        persona = self.mongo.get_persona(phone)

        if persona and persona.get("numerology") and self._should_send_welcome_back(message):
            returning_ctx = self.memory.get_returning_user_context(phone, profile=profile, persona=persona)
            if returning_ctx.get("is_returning"):
                welcome = self._build_welcome_back_prompt(returning_ctx)
                logger.info("Sending welcome-back continuation prompt phone=%s", phone)
                self._send_reply(phone, welcome)
                logger.info("QUERY_END id=%s phone=%s handled_by=welcome_back", query_id, phone)
                return

        # Unified intent router for known users/conversations.
        handled = await self._route_intent(phone, message, profile, persona, query_id)
        if handled:
            logger.info("QUERY_END id=%s phone=%s handled_by=intent_router", query_id, phone)
            return

        # No persona yet: run numerology, store, and send reading
        self._log_tool_call(phone, query_id, "astrology_agent.fetch")
        astro = self.astro.fetch(profile)
        logger.info("No persona yet for phone=%s; running onboarding handover to numerology", phone)
        progress_msg = "⏳ Calculating your astrology & numerology profile... one moment."
        self._send_reply(phone, progress_msg)
        await asyncio.sleep(2.2)
        self._log_tool_call(phone, query_id, "numerology_agent.call")
        numero_result = await call_numerology_agent(profile)
        if isinstance(numero_result, dict) and numero_result.get("data") is not None and numero_result.get("message") is not None:
            if isinstance(astro, dict) and astro:
                self.mongo.store_astrology(phone, astro)
            self.mongo.store_numerology(phone, numero_result["data"])
            self.mongo.store_persona_numerology(phone, numero_result["data"])  # persona in astro_data for follow-up context
            logger.info("Numerology generated and stored for phone=%s", phone)
            self._send_reply(phone, numero_result["message"])
            curiosity_nudge = self._build_curiosity_followup(numero_result["data"])
            if curiosity_nudge:
                self._send_reply(phone, curiosity_nudge)
        else:
            error_msg = numero_result.get("message", "Something went wrong. Please try again! 🌟") if isinstance(numero_result, dict) else str(numero_result)
            logger.warning("Numerology generation failed for phone=%s", phone)
            self._send_reply(phone, error_msg)
        logger.info("QUERY_END id=%s phone=%s handled_by=numerology", query_id, phone)

    def _send_reply(self, phone: str, text: str):
        msg = str(text or "").strip()
        if not msg:
            return
        send_whatsapp_message(phone, msg)
        self.memory.store_short(phone, "assistant", msg)

    @staticmethod
    def _log_tool_call(phone: str, query_id: str, tool_name: str, **meta):
        logger.info(
            "TOOL_CALL query_id=%s phone=%s tool=%s meta=%s",
            query_id,
            phone,
            tool_name,
            meta or {},
        )

    @staticmethod
    def _normalize_dob_for_kundli(dob_raw: str) -> str | None:
        text = (dob_raw or "").strip()
        if not text:
            return None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_tob_for_kundli(tob_raw: str) -> str:
        text = (tob_raw or "").strip()
        if not text or text.lower() == "unknown":
            return "12:00"
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
            try:
                return datetime.strptime(text, fmt).strftime("%H:%M")
            except ValueError:
                continue
        return "12:00"

    @staticmethod
    def _compact_kundli_reply(reply: str) -> str:
        """
        Safety net: if upstream returns verbose/raw JSON content, reduce to readable lines.
        """
        text = (reply or "").strip()
        if not text:
            return "I could not format your kundli right now. Please try again."
        if "Detailed JSON" not in text and len(text) <= 1800:
            return text

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        kept: list[str] = []
        for ln in lines:
            if ln.startswith("Detailed JSON"):
                break
            kept.append(ln)
            if len(kept) >= 10:
                break

        if not kept:
            # Last-resort minimal summary
            return (
                "🔮 Detailed Kundli Ready\n"
                "Your kundli was generated successfully.\n"
                "Reply with 'explain my dasha' or 'explain mangal dosha' for detailed guidance."
            )

        kept.append("Reply with 'explain my dasha' or 'explain mangal dosha' for deeper details.")
        compact = "\n".join(dict.fromkeys(kept))
        return compact[:1800].strip()

    async def _route_intent(self, phone: str, message: str, profile: dict, persona: dict | None, query_id: str) -> bool:
        """
        Central router for existing user intents:
        - daily_prediction -> MCP daily horoscope
        - kundli_request   -> MCP kundli
        - fallback         -> follow-up LLM (when persona exists)
        """
        mapped_topic = None
        if persona and persona.get("numerology"):
            mapped_topic, _ = self.follow_up.map_topic_message(message)
        if str(message or "").strip() == "4" or mapped_topic == "daily_horoscope":
            intent, params = "daily_prediction", {}
        else:
            intent, params = classify_intent(message)
        logger.info("Intent router phone=%s intent=%s params=%s", phone, intent, params)

        if intent == "daily_prediction":
            sign = (params.get("sign") or "").strip()
            if not sign:
                sign = dob_to_sun_sign((profile.get("dob") if isinstance(profile, dict) else "") or "")
            if not sign:
                self._send_reply(phone, "I need your birth date to send your daily horoscope. What's your DOB? 🌟")
                return True
            today = date.today().isoformat()
            logger.info("Calling MCP daily_horoscope phone=%s sign=%s date=%s", phone, sign, today)
            user_name = (profile.get("name") or "").strip() if isinstance(profile, dict) else ""
            persona_context = self._build_daily_persona_context(persona)
            self._log_tool_call(phone, query_id, "mcp.get_daily_horoscope", intent=intent, sign=sign, date=today)
            result = await mcp_call_tool(
                MCP_SERVER_URL,
                "get_daily_horoscope",
                {
                    "sign": sign,
                    "date": today,
                    "user_name": user_name,
                    "persona_context": persona_context,
                },
            )
            reply = result if isinstance(result, str) else str(result)
            logger.info("MCP daily_horoscope response chars=%d phone=%s", len(reply), phone)
            self._send_reply(phone, reply)
            return True

        if intent == "kundli_generation":
            dob = self._normalize_dob_for_kundli((profile.get("dob") if isinstance(profile, dict) else "") or "")
            tob = self._normalize_tob_for_kundli((profile.get("tob") if isinstance(profile, dict) else "") or "")
            place = ((profile.get("pob") if isinstance(profile, dict) else "") or "").strip()
            if not place:
                place = ((profile.get("place") if isinstance(profile, dict) else "") or "").strip()
            lat_raw = ((profile.get("pob_lat") if isinstance(profile, dict) else "") or "").strip()
            lon_raw = ((profile.get("pob_lon") if isinstance(profile, dict) else "") or "").strip()
            tz = ((profile.get("pob_timezone") if isinstance(profile, dict) else "") or "").strip()

            lat = None
            lon = None
            try:
                lat = float(lat_raw) if lat_raw else None
                lon = float(lon_raw) if lon_raw else None
            except (TypeError, ValueError):
                lat = None
                lon = None

            missing = []
            if not dob:
                missing.append("date of birth")
            if not place:
                missing.append("place of birth")
            if missing:
                self._send_reply(
                    phone,
                    "To generate your kundli, I still need your "
                    + " and ".join(missing)
                    + ". Please share it in this chat. 🔮",
                )
                return True

            self._log_tool_call(phone, query_id, "mcp.get_kundli", intent=intent)
            result = await mcp_call_tool(
                MCP_SERVER_URL,
                "get_kundli",
                {
                    "date_of_birth": dob,
                    "time_of_birth": tob,
                    "place": place,
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": tz or None,
                    "ayanamsa": "1",
                    "la": "en",
                    "year_length": 1,
                    "include_dasha_periods": True,
                    "include_mangal_dosha": True,
                },
            )
            reply = result if isinstance(result, str) else str(result)
            reply = self._compact_kundli_reply(reply)
            logger.info("MCP get_kundli response chars=%d phone=%s", len(reply), phone)
            self._send_reply(phone, reply)
            return True

        if intent in ("dasha_detail", "mangal_dosha_detail"):
            dob = self._normalize_dob_for_kundli((profile.get("dob") if isinstance(profile, dict) else "") or "")
            tob = self._normalize_tob_for_kundli((profile.get("tob") if isinstance(profile, dict) else "") or "")
            place = ((profile.get("pob") if isinstance(profile, dict) else "") or "").strip()
            if not place:
                place = ((profile.get("place") if isinstance(profile, dict) else "") or "").strip()
            lat_raw = ((profile.get("pob_lat") if isinstance(profile, dict) else "") or "").strip()
            lon_raw = ((profile.get("pob_lon") if isinstance(profile, dict) else "") or "").strip()
            tz = ((profile.get("pob_timezone") if isinstance(profile, dict) else "") or "").strip()
            try:
                lat = float(lat_raw) if lat_raw else None
                lon = float(lon_raw) if lon_raw else None
            except (TypeError, ValueError):
                lat = None
                lon = None

            missing = []
            if not dob:
                missing.append("date of birth")
            if not place:
                missing.append("place of birth")
            if missing:
                self._send_reply(
                    phone,
                    "To explain this, I still need your " + " and ".join(missing) + ". Please share it in this chat. 🔮",
                )
                return True

            tool_name = "get_dasha_details" if intent == "dasha_detail" else "get_mangal_dosha_details"
            self._log_tool_call(phone, query_id, f"mcp.{tool_name}", intent=intent)
            result = await mcp_call_tool(
                MCP_SERVER_URL,
                tool_name,
                {
                    "date_of_birth": dob,
                    "time_of_birth": tob,
                    "place": place,
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": tz or None,
                    "ayanamsa": "1",
                    "la": "en",
                    "year_length": 1,
                },
            )
            reply = result if isinstance(result, str) else str(result)
            logger.info("MCP %s response chars=%d phone=%s", tool_name, len(reply), phone)
            self._send_reply(phone, reply)
            return True

        if persona and persona.get("numerology"):
            logger.info("Routing to follow-up agent for phone=%s", phone)
            memory_context = self.memory.get_memory_context(phone)
            enhanced_message = (
                message
                + "\n\n[Phone memory context]\n"
                + memory_context
                if memory_context
                else message
            )
            # Hybrid topic routing: numeric choices and free-text topic asks.
            mapped_topic, mapped_prompt = self.follow_up.map_topic_message(message)
            if str(message or "").strip() == "4" or any(k in str(message or "").lower() for k in ("today horoscope", "daily horoscope", "daily prediction", "today's horoscope")):
                mapped_topic = "daily_horoscope"
            if mapped_prompt:
                logger.info("Mapped topic selection phone=%s topic=%s", phone, mapped_topic)
                enhanced_message = mapped_prompt
            self._log_tool_call(phone, query_id, "follow_up_agent.answer", intent=intent)
            reply = self.follow_up.answer(phone, enhanced_message, persona)
            logger.info("Follow-up response chars=%d phone=%s", len(reply), phone)
            self._send_reply(phone, reply)
            return True

        return False
