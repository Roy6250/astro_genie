"""Pydantic models for structured numerology readings (single source of truth for storage and display)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CalculatedFrom(BaseModel):
    """Audit and future prompts: what inputs were used for the reading."""

    dob: str = Field(..., description="Date of birth, e.g. DD-MM-YYYY")
    name_used: bool = Field(..., description="Whether full name was provided")
    place_used: bool = Field(..., description="Whether place was provided")


class LuckyColor(BaseModel):
    """A lucky color with a short reason."""

    name: str = Field(..., description="Color name, e.g. emerald green")
    reason: str = Field(..., description="Brief reason, e.g. Jupiter's glow")


class LuckyDay(BaseModel):
    """A lucky day with a short reason."""

    day: str = Field(..., description="Day name, e.g. Wednesday")
    reason: str = Field(..., description="Brief reason, e.g. Mercury")


class LuckyStone(BaseModel):
    """Lucky stone with explanation."""

    name: str = Field(..., description="Stone name")
    explanation: str = Field(..., description="Why it suits the profile")


# --- Core calculated (deterministic, no LLM) ---
# These are filled from calculation helpers; traits can be from a lookup table or LLM later.


class NumerologyReading(BaseModel):
    """Full numerology reading: calculated numbers, traits, and generated content. Stored in Mongo and used to build the display message."""

    # Core calculated
    life_path_number: int = Field(..., ge=1, le=9, description="Life path number 1–9")
    mulank: int = Field(..., ge=1, le=9, description="Mulank 1–9")
    destiny_number: Optional[int] = Field(None, ge=1, le=9, description="Destiny number when name provided")
    life_path_traits: str = Field(..., description="Traits for life path number")
    mulank_traits: str = Field(..., description="Traits for mulank")
    destiny_traits: Optional[str] = Field(None, description="Traits for destiny number when name provided")

    # What was used for calculation
    calculated_from: CalculatedFrom = Field(..., description="Inputs used for this reading")

    # Generated reading (from one LLM call returning JSON)
    lucky_numbers: list[int] = Field(default_factory=list, description="e.g. [3, 5, 6, 9]")
    today_vibe_number: Optional[int] = Field(None, ge=1, le=9, description="Today's vibe number")
    lucky_colors: list[LuckyColor] = Field(default_factory=list, description="Colors with reasons")
    lucky_days: list[LuckyDay] = Field(default_factory=list, description="Days with reasons")
    lucky_stone: Optional[LuckyStone] = Field(None, description="Lucky stone and explanation")
    power_phrase: str = Field("", description="e.g. The Starlit Storyteller")
    quick_tip: str = Field("", description="Short actionable tip")
    follow_up_question: str = Field("", description="Suggested follow-up question")

    # Optional for future responses
    personality_summary: Optional[str] = Field(None, description="Brief personality summary")
    main_challenge: Optional[str] = Field(None, description="Main challenge to work on")
    suggested_follow_ups: list[str] = Field(
        default_factory=list,
        description="e.g. ['personal year', 'love compatibility', 'current transit']",
    )

    # Meta
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="When the reading was generated (for caching / last reading)")


class NumerologyOutput(BaseModel):
    """Return type of call_numerology_agent: structured data for storage and formatted message for the user."""

    data: NumerologyReading = Field(..., description="Validated reading to store in Mongo")
    message: str = Field(..., description="Formatted user-facing message (e.g. for WhatsApp)")
