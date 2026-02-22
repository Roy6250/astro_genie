from fastapi import APIRouter
from pydantic import BaseModel
from workers.celery_worker import process_message_task
from core.orchestrator import Orchestrator
router = APIRouter()

class IncomingMsg(BaseModel):
    phone: str
    message: str

@router.post("/simulate-message")
async def simulate_message(data: IncomingMsg):
    # process_message_task.delay(data.phone, data.message)

    print(data.message)

    await Orchestrator().handle_message(data.phone, data.message)
    
    return {"status": "queued"}
