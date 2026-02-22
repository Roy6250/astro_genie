from services.llm_service import call_llm

class InterpretationAgent:

    def generate(self, profile, astro, numero, question):

        prompt = f"""
            User Profile: {profile}
            Astrology Data: {astro}
            Numerology Data: {numero}
            User Question: {question}
            Respond as calm astrology guide.
"""

        return call_llm(prompt)
