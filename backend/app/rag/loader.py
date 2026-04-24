import json
from langchain_core.documents import Document
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent.parent / "output" / "unsw_8543_courses.json"


def load_course_documents() -> list[Document]:
    """Load the UNSW course JSON and convert each entry into a LangChain Document.

    page_content is a structured text block optimised for embedding — it includes
    all meaningful fields so retrieval captures constraints, delivery modes, etc.
    Metadata stores scalar fields used for post-retrieval display.
    """
    with open(DATA_PATH, encoding="utf-8") as f:
        courses: list[dict] = json.load(f)

    documents: list[Document] = []
    for course in courses:
        # --- Format array fields as readable text ---
        equiv = ", ".join(course.get("equivalent_courses") or []) or "None"

        delivery_lines = []
        for d in course.get("delivery") or []:
            delivery_lines.append(
                f"  - {d['delivery_mode']} / {d['delivery_format']} "
                f"({d['contact_hours']}h contact)"
            )
        delivery_text = "\n".join(delivery_lines) or "  - Not specified"

        # --- Build rich page_content for embedding ---
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

        metadata = {
            "course_code": course["course_code"],
            "course_name": course["course_name"],
            "units_of_credit": course["units_of_credit"],
            "offering_terms": course.get("offering_terms", ""),
            "campus": course.get("campus", ""),
            "faculty": course.get("faculty", ""),
            "url": course.get("url", ""),
        }

        documents.append(Document(page_content="\n".join(parts), metadata=metadata))

    print(f"[Loader] Loaded {len(documents)} course documents from {DATA_PATH.name}")
    return documents
