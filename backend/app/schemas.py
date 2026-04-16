from pydantic import BaseModel
from typing import List, Optional


class DeliveryInfo(BaseModel):
    display: str
    delivery_mode: str
    delivery_format: str
    contact_hours: str


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
