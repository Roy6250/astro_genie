from celery import Celery
from config import REDIS_URL
from core.orchestrator import Orchestrator
import asyncio

celery = Celery("astro", broker=REDIS_URL)
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@celery.task
def process_message_task(phone, message):
    logger.info("Starting with phone=%s, message=%r", phone, message)
    asyncio.run(Orchestrator().handle_message(phone, message))
    logger.info("Finished processing message for %s", phone)