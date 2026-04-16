import pandas as pd
from langchain_core.documents import Document
from pathlib import Path

# E:/CourseCompass/output/unsw_8543_courses.csv
DATA_PATH = Path(__file__).parent.parent.parent.parent / "output" / "unsw_8543_courses.csv"


def load_course_documents() -> list[Document]:
    """Load the UNSW course CSV and convert each row into a LangChain Document.

    The page_content is a structured text block optimised for embedding.
    All course fields are also stored in metadata for retrieval-time filtering.
    """
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig").fillna("")

    documents: list[Document] = []
    for _, row in df.iterrows():
        content = (
            f"Course: {row['course_code']} - {row['course_name']}\n"
            f"Units of Credit: {row['units_of_credit']}\n"
            f"Faculty: {row['faculty']}\n"
            f"Offering Terms: {row['offering_terms']}\n"
            f"Campus: {row['campus']}\n"
            f"Overview: {row['overview']}"
        )

        metadata = {
            "course_code": row["course_code"],
            "course_name": row["course_name"],
            "units_of_credit": row["units_of_credit"],
            "offering_terms": row["offering_terms"],
            "campus": row["campus"],
            "faculty": row["faculty"],
        }

        documents.append(Document(page_content=content, metadata=metadata))

    print(f"[Loader] Loaded {len(documents)} course documents from {DATA_PATH.name}")
    return documents
