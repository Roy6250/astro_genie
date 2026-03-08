from memory.mongo_manager import MongoManager
from agents.onboarding_agent import OnboardingAgent

mongo = MongoManager()
onboarding_agent = OnboardingAgent(mongo)

class StateMachine:

    def handle(self, phone, message):
        return onboarding_agent.handle(phone, message)
