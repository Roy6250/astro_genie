class FormatterAgent:

    def format_reading(self, text, numero):

        return f"""
✨ Your Astro Genie Reading ✨

🔢 Life Path Number: {numero['life_path']}
You are naturally {numero['traits']}.

🌙 Personality Insight:
{text}

Would you like to know more about:
1. Career
2. Love
3. Money
4. Timing
"""
