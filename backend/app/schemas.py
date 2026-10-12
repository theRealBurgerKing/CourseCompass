from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

# Chat input limits. The new message is rejected when over the limit; history is trimmed instead,
# because the frontend sends the whole conversation and the RAG chain only uses the last 20 turns.
MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_ITEMS = 20
MAX_HISTORY_ITEM_CHARS = 8000


class DeliveryInfo(BaseModel):
    display: str
    delivery_mode: str
    delivery_format: str
    contact_hours: str


# ── Chat ────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str = Field(default="default", max_length=128)  # deprecated: unused by the backend
    history: List[HistoryItem] = []   # recent messages for multi-turn context

    @field_validator("history")
    @classmethod
    def _trim_history(cls, items: List[HistoryItem]) -> List[HistoryItem]:
        return [
            HistoryItem(role=i.role, content=i.content[:MAX_HISTORY_ITEM_CHARS])
            for i in items[-MAX_HISTORY_ITEMS:]
        ]


class CourseSource(BaseModel):
    course_code: str
    course_name: str
    units_of_credit: str
    offering_terms: str
    faculty: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[CourseSource]
    conversation_id: str


# ── Courses ─────────────────────────────────────────────────

class CourseItem(BaseModel):
    course_code: str
    url: str
    course_name: str
    units_of_credit: str
    overview: str
    additional_enrolment_constraints: str
    equivalent_courses: List[str]
    delivery: List[DeliveryInfo]
    offering_terms: str
    campus: str
    faculty: str
    notes: str
