from core.state_machine import StateMachine
from memory.mongo_manager import MongoManager
from agents.astrology_agent import AstrologyAgent
from agents.numerology_agent import call_numerology_agent
from agents.interpretation_agent import InterpretationAgent
from agents.formatter_agent import FormatterAgent
from agents.follow_up_agent import FollowUpAgent
from services.whatsapp_service import send_whatsapp_message

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

        # User already has a reading in astro_data — answer follow-up using their context
        if persona and persona.get("numerology"):
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
