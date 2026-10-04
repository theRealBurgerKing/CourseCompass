import json
import re
from functools import lru_cache
from langchain_core.documents import Document
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent.parent / "output" / "unsw_8543_courses.json"
ENRICHMENT_PATH = Path(__file__).parent.parent.parent / "output" / "course_enrichment.json"


def parse_terms(offering_terms: str) -> set[str]:
    """'Summer Term, Term 1' -> {'Summer Term', 'Term 1'}; empty string -> empty set."""
    return {t.strip() for t in (offering_terms or "").split(",") if t.strip()}


def _load_courses() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_enrichment() -> dict[str, dict]:
    """Optional LLM-generated search aids keyed by course code (see scripts/enrich_courses.py)."""
    if not ENRICHMENT_PATH.exists():
        return {}
    with open(ENRICHMENT_PATH, encoding="utf-8") as f:
        return json.load(f)


def render_course_text(course: dict) -> str:
    """The factual course text shown to the LLM — source data only, no generated content."""
    equiv = ", ".join(course.get("equivalent_courses") or []) or "None"

    delivery_lines = []
    for d in course.get("delivery") or []:
        delivery_lines.append(
            f"  - {d['delivery_mode']} / {d['delivery_format']} "
            f"({d['contact_hours']}h contact)"
        )
    delivery_text = "\n".join(delivery_lines) or "  - Not specified"

    parts = [
        f"Course Code: {course['course_code']}",
        f"Course Name: {course['course_name']}",
        f"Units of Credit: {course['units_of_credit']}",
        f"Faculty: {course['faculty']}",
        f"Offering Terms: {course['offering_terms']}",
        f"Campus: {course['campus']}",
        f"Overview: {course['overview']}",
        f"Delivery:\n{delivery_text}",
        f"Equivalent Courses: {equiv}",
    ]
    if course.get("additional_enrolment_constraints"):
        parts.append(f"Enrolment Constraints: {course['additional_enrolment_constraints']}")
    if course.get("notes"):
        parts.append(f"Notes: {course['notes']}")
    return "\n".join(parts)


def _render_search_aids(aids: dict) -> str:
    """Retrieval-only block: Chinese summary + bilingual keywords, so Chinese queries match English courses."""
    lines = []
    if aids.get("summary_zh"):
        lines.append(f"中文简介: {aids['summary_zh']}")
    if aids.get("keywords_zh"):
        lines.append(f"中文关键词: {', '.join(aids['keywords_zh'])}")
    if aids.get("keywords_en"):
        lines.append(f"English Keywords: {', '.join(aids['keywords_en'])}")
    if aids.get("suitable_for_zh"):
        lines.append(f"适合人群: {aids['suitable_for_zh']}")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def course_texts() -> dict[str, str]:
    """course_code -> factual text for the LLM context."""
    return {c["course_code"]: render_course_text(c) for c in _load_courses()}


def load_course_documents() -> list[Document]:
    """Convert each course into one Document for indexing.

    page_content = factual text + (if available) retrieval-only search aids; this is what gets
    embedded and BM25-indexed. The LLM never sees the aids — it gets render_course_text() via
    course_texts(), so generated text can't be mistaken for course facts.
    Metadata stores scalar fields used for post-retrieval display.
    """
    courses = _load_courses()
    enrichment = _load_enrichment()

    documents: list[Document] = []
    for course in courses:
        content = render_course_text(course)
        aids = enrichment.get(course["course_code"])
        if aids:
            content += "\n" + _render_search_aids(aids)

        metadata = {
            "course_code": course["course_code"],
            "course_name": course["course_name"],
            "units_of_credit": course["units_of_credit"],
            "offering_terms": course.get("offering_terms", ""),
            "campus": course.get("campus", ""),
            "faculty": course.get("faculty", ""),
            "url": course.get("url", ""),
        }

        documents.append(Document(page_content=content, metadata=metadata))

    enriched = sum(1 for c in courses if c["course_code"] in enrichment)
    print(f"[Loader] Loaded {len(documents)} course documents from {DATA_PATH.name} ({enriched} enriched)")
    return documents
