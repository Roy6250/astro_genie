from memory.mongo_manager import MongoManager
import re

mongo = MongoManager()

class StateMachine:

    def handle(self, phone, message):
        state = mongo.get_state(phone)

        if state == "NEW_USER":
            mongo.update_state(phone, "ASK_DOB")
            return ENTRY_MSG

        if state == "ASK_DOB":
            if not re.match(r"\d{2}-\d{2}-\d{4}", message):
                return "Please enter DOB in DD-MM-YYYY format 😊"
            mongo.save_profile_field(phone, "dob", message)
            mongo.update_state(phone, "ASK_TOB")
            return "Thank you ✨ What is your Time of Birth? (or type Unknown)"

        if state == "ASK_TOB":
            tob = message if message.lower() != "unknown" else "12:00"
            mongo.save_profile_field(phone, "tob", tob)
            mongo.update_state(phone, "ASK_POB")
            return "Got it 🌍 Please tell me your Place of Birth (City, Country)"

        if state == "ASK_POB":
            mongo.save_profile_field(phone, "pob", message)
            mongo.update_state(phone, "ASK_NAME")
            return "Almost done ✨ What is your Full Name?"

        if state == "ASK_NAME":
            mongo.save_profile_field(phone, "name", message)
            mongo.update_state(phone, "PROFILE_READY")
            return "🔮 Thank you! Preparing your reading..."

        return None


ENTRY_MSG = """✨ Hi, I’m Astro Genie 🔮  
I help you understand your life through astrology & numerology.  
Let’s begin 🌙 What is your Date of Birth? (DD-MM-YYYY)"""
