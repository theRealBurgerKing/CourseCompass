from fastapi import APIRouter, HTTPException, Query
from app.schemas import CourseItem
from typing import List, Optional
import pandas as pd
from pathlib import Path
from functools import lru_cache

router = APIRouter()

DATA_PATH = (
    Path(__file__).parent.parent.parent.parent / "output" / "unsw_8543_courses.csv"
)


@lru_cache(maxsize=1)
def _load_df() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH, encoding="utf-8-sig").fillna("")


@router.get("/courses", response_model=List[CourseItem])
async def list_courses(
    q: Optional[str] = Query(None, description="Keyword search in code, name, or overview"),
    faculty: Optional[str] = Query(None, description="Filter by faculty name (partial match)"),
    term: Optional[str] = Query(None, description="Filter by offering term, e.g. 'Term 1'"),
):
    """List all courses with optional keyword, faculty, and term filters."""
    df = _load_df().copy()

    if q:
        mask = (
            df["course_code"].str.contains(q, case=False, na=False)
            | df["course_name"].str.contains(q, case=False, na=False)
            | df["overview"].str.contains(q, case=False, na=False)
        )
        df = df[mask]

    if faculty:
        df = df[df["faculty"].str.contains(faculty, case=False, na=False)]

    if term:
        df = df[df["offering_terms"].str.contains(term, case=False, na=False)]

    return df.to_dict(orient="records")


@router.get("/courses/{course_code}", response_model=CourseItem)
async def get_course(course_code: str):
    """Retrieve a single course by its code (case-insensitive)."""
    df = _load_df()
    row = df[df["course_code"] == course_code.upper()]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found.")
    return row.iloc[0].to_dict()
