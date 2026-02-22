from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class UserProfile(BaseModel):
    phone: str
    name: Optional[str]
    dob: Optional[str]
    tob: Optional[str]
    pob: Optional[str]


class UserState(BaseModel):
    phone: str
    state: str  # FSM state
    updated_at: datetime


class AstrologyData(BaseModel):
    phone: str
    data: Dict
    created_at: datetime


class NumerologyData(BaseModel):
    phone: str
    data: Dict
    created_at: datetime


class ConversationMessage(BaseModel):
    phone: str
    role: str  # "user" / "assistant"
    message: str
    timestamp: datetime


class UserInsight(BaseModel):
    phone: str
    tag: str  # e.g. "career_anxiety"
    value: str
    confidence: float
    created_at: datetime
