from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from pathlib import Path

# Stored at E:/CourseCompass/backend/faiss_index/
INDEX_PATH = Path(__file__).parent.parent.parent / "faiss_index"

_vectorstore: FAISS | None = None


def get_vectorstore() -> FAISS:
    """Return the singleton FAISS vectorstore, loading or building it as needed."""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = _load_or_build()
    return _vectorstore


def build_vectorstore() -> FAISS:
    """Force-rebuild the FAISS index from the source CSV and persist it to disk."""
    from .loader import load_course_documents

    print("[FAISS] Building index from CSV...")
    documents = load_course_documents()
    embeddings = _get_embeddings()
    vs = FAISS.from_documents(documents, embeddings)

    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(INDEX_PATH))
    print(f"[FAISS] Index saved to {INDEX_PATH} ({len(documents)} documents)")
    return vs


def _load_or_build() -> FAISS:
    embeddings = _get_embeddings()

    if (INDEX_PATH / "index.faiss").exists():
        print(f"[FAISS] Loading existing index from {INDEX_PATH}")
        return FAISS.load_local(
            str(INDEX_PATH),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    print("[FAISS] No existing index found — building from scratch...")
    return build_vectorstore()


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model="text-embedding-3-small")
