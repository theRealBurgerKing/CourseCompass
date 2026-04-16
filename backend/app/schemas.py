from pydantic import BaseModel
from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class CourseSource(BaseModel):
    course_code: str
    course_name: str
    units_of_credit: str
    offering_terms: str
    faculty: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[CourseSource]
    session_id: str


class CourseItem(BaseModel):
    course_code: str
    course_name: str
    units_of_credit: str
    overview: str
    offering_terms: str
    campus: str
    faculty: str
