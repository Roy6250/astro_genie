from utils.custom_llm import OurLLM
import logging

llm = OurLLM()
logger = logging.getLogger(__name__)


def call_llm(prompt):
    prompt_text = str(prompt or "")
    logger.info("LLM request chars=%d", len(prompt_text))
    response = llm.complete(prompt)
    text = response.text.strip()   # .text gives the clean string output
    logger.info("LLM response chars=%d", len(text))
    return text