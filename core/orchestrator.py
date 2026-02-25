from datetime import date

from config import MCP_SERVER_URL
from core.state_machine import StateMachine
from memory.mongo_manager import MongoManager
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
logging.basicConfig(level=logging.INFO)                         # Configure logging for MCP server calls                                                                        

class Orchestrator:

    def __init__(self):
        self.fsm = StateMachine()
        self.mongo = MongoManager()
        self.astro = AstrologyAgent()
        self.interpreter = InterpretationAgent()
        self.formatter = FormatterAgent()
        self.follow_up = FollowUpAgent()

    async def handle_message(self, phone, message):

        print("Inside")

        fsm_reply = self.fsm.handle(phone, message)
        print(fsm_reply)
        if fsm_reply:
            send_whatsapp_message(phone, fsm_reply)
            return

        profile = self.mongo.get_profile(phone)
        persona = self.mongo.get_persona(phone)

        # User already has a reading — run intent then either daily horoscope or follow-up
        if persona and persona.get("numerology"):
            intent, params = classify_intent(message)
            if intent == "daily_prediction":
                sign = (params.get("sign") or "").strip()
                if not sign:
                    sign = dob_to_sun_sign(profile.get("dob") or "")
                if not sign:
                    send_whatsapp_message(
                        phone,
                        "I need your birth date to send your daily horoscope. What's your DOB? 🌟",
                    )
                    return
                today = date.today().isoformat()
                logging.info(f"Calling MCP server for daily horoscope for sign: {sign}, date: {today}")
                result = await mcp_call_tool(
                    MCP_SERVER_URL,
                    "get_daily_horoscope",
                    {"sign": sign, "date": today},
                )
                reply = result if isinstance(result, str) else str(result)
                send_whatsapp_message(phone, reply)
                return
            reply = self.follow_up.answer(phone, message, persona)
            send_whatsapp_message(phone, reply)
            return

        # No persona yet: run numerology, store, and send reading
        astro = self.astro.fetch(profile)
        print(profile)
        numero_result = await call_numerology_agent(profile)
        if isinstance(numero_result, dict) and numero_result.get("data") is not None and numero_result.get("message") is not None:
            self.mongo.store_numerology(phone, numero_result["data"])
            self.mongo.store_persona_numerology(phone, numero_result["data"])  # persona in astro_data for follow-up context
            send_whatsapp_message(phone, numero_result["message"])
        else:
            error_msg = numero_result.get("message", "Something went wrong. Please try again! 🌟") if isinstance(numero_result, dict) else str(numero_result)
            send_whatsapp_message(phone, error_msg)
