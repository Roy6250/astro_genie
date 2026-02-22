from pymongo import MongoClient, ASCENDING
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class MongoManager:

    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")  # set in .env
        self.client = MongoClient(mongo_uri)

        self.db = self.client["astro_genie"]

        # Collections
        self.users = self.db["users"]
        self.states = self.db["states"]
        self.chat_history = self.db["chat_history"]
        self.astro_data = self.db["astro_data"]
        self.numero_data = self.db["numero_data"]
        self.insights = self.db["insights"]

        self._create_indexes()

    # ------------------ INDEXES ------------------

    def _create_indexes(self):
        self.users.create_index([("phone", ASCENDING)], unique=True)
        self.states.create_index([("phone", ASCENDING)], unique=True)
        self.chat_history.create_index([("phone", ASCENDING)])
        self.astro_data.create_index([("phone", ASCENDING)])
        self.numero_data.create_index([("phone", ASCENDING)])

    # ------------------ FSM STATE ------------------

    def get_state(self, phone: str) -> str:
        doc = self.states.find_one({"phone": phone})
        return doc["state"] if doc else "NEW_USER"

    def update_state(self, phone: str, state: str):
        self.states.update_one(
            {"phone": phone},
            {"$set": {"state": state, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    # ------------------ PROFILE ------------------

    def save_profile_field(self, phone: str, field: str, value: str):
        self.users.update_one(
            {"phone": phone},
            {"$set": {field: value, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    def get_profile(self, phone: str) -> dict:
        doc = self.users.find_one({"phone": phone})
        return doc if doc else {}

    # ------------------ CHAT MEMORY ------------------

    def store_message(self, phone: str, role: str, message: str):
        self.chat_history.insert_one({
            "phone": phone,
            "role": role,
            "message": message,
            "timestamp": datetime.utcnow()
        })

    def get_recent_messages(self, phone: str, limit: int = 5):
        return list(
            self.chat_history.find({"phone": phone})
            .sort("timestamp", -1)
            .limit(limit)
        )

    # ------------------ ASTROLOGY / PERSONA DATA ------------------
    # astro_data = one doc per user who completed registration; "data" holds persona (numerology, astrology)
    # so we can answer follow-up questions with full context.

    def store_astrology(self, phone: str, data: dict):
        """Store or overwrite astrology slice of persona."""
        self.astro_data.update_one(
            {"phone": phone},
            {"$set": {"data.astrology": data, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    def store_persona_numerology(self, phone: str, numerology_data: dict):
        """Merge numerology reading into astro_data (persona) for this user. Does not overwrite astrology."""
        self.astro_data.update_one(
            {"phone": phone},
            {"$set": {"data.numerology": numerology_data, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    def get_astrology(self, phone: str):
        doc = self.astro_data.find_one({"phone": phone})
        if not doc or "data" not in doc:
            return None
        data = doc["data"]
        if isinstance(data, dict) and "astrology" in data:
            return data["astrology"]
        # Old format: data was the astrology blob directly
        return data

    def get_persona(self, phone: str) -> dict | None:
        """Full persona (numerology + astrology) for users who completed registration."""
        doc = self.astro_data.find_one({"phone": phone})
        return doc.get("data") if doc and isinstance(doc.get("data"), dict) else None

    # ------------------ NUMEROLOGY DATA ------------------

    def store_numerology(self, phone: str, data: dict):
        self.numero_data.update_one(
            {"phone": phone},
            {"$set": {"data": data, "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    def get_numerology(self, phone: str):
        doc = self.numero_data.find_one({"phone": phone})
        return doc["data"] if doc else None

    # ------------------ INSIGHTS (LLM-INFERRED) ------------------

    def store_insight(self, phone: str, tag: str, value: str, confidence: float):
        self.insights.insert_one({
            "phone": phone,
            "tag": tag,
            "value": value,
            "confidence": confidence,
            "created_at": datetime.utcnow()
        })

    def get_insights(self, phone: str):
        return list(self.insights.find({"phone": phone}))
