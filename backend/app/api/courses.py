import json
from fastapi import APIRouter, HTTPException, Query
from app.schemas import CourseItem
from typing import List, Optional
from pathlib import Path
from functools import lru_cache

router = APIRouter()

DATA_PATH = (
    Path(__file__).parent.parent.parent.parent / "output" / "unsw_8543_courses.json"
)


@lru_cache(maxsize=1)
def _load_courses() -> tuple[dict, ...]:
    """Load JSON once and return as an immutable tuple (hashable for lru_cache)."""
    with open(DATA_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


def _matches(course: dict, q: Optional[str], faculty: Optional[str], term: Optional[str]) -> bool:
    if q:
        q_lower = q.lower()
        searchable = " ".join([
            course.get("course_code", ""),
            course.get("course_name", ""),
            course.get("overview", ""),
        ]).lower()
        if q_lower not in searchable:
            return False
    if faculty and faculty.lower() not in course.get("faculty", "").lower():
        return False
    if term and term.lower() not in course.get("offering_terms", "").lower():
        return False
    return True


@router.get("/courses", response_model=List[CourseItem])
async def list_courses(
    q: Optional[str] = Query(None, description="Keyword search in code, name, or overview"),
    faculty: Optional[str] = Query(None, description="Filter by faculty name (partial match)"),
    term: Optional[str] = Query(None, description="Filter by offering term, e.g. 'Term 1'"),
):
    """List all courses with optional keyword, faculty, and term filters."""
    courses = _load_courses()
    return [c for c in courses if _matches(c, q, faculty, term)]


@router.get("/courses/{course_code}", response_model=CourseItem)
async def get_course(course_code: str):
    """Retrieve a single course by its code (case-insensitive)."""
    target = course_code.upper()
    for course in _load_courses():
        if course["course_code"] == target:
            return course
    raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found.")
