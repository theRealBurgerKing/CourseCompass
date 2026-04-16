"""Hybrid retriever: BM25 (keyword) + FAISS (semantic) fused with Reciprocal Rank Fusion.

BM25 gives exact course-code matches near-perfect recall.
FAISS captures semantic similarity for natural-language queries.
RRF combines both rankings without needing score normalisation.
"""
import re
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from .vectorstore import get_vectorstore
from .loader import load_course_documents

# ---------------------------------------------------------------------------
# BM25 singleton
# ---------------------------------------------------------------------------

_bm25: BM25Okapi | None = None
_bm25_docs: list[Document] | None = None


def _tokenize(text: str) -> list[str]:
    """Split on non-alphanumeric boundaries, uppercase — preserves COMP9021 as one token."""
    return re.findall(r'[A-Za-z0-9]+', text.upper())


def _get_bm25() -> tuple[BM25Okapi, list[Document]]:
    global _bm25, _bm25_docs
    if _bm25 is None:
        docs = load_course_documents()
        corpus = [_tokenize(d.page_content) for d in docs]
        _bm25 = BM25Okapi(corpus)
        _bm25_docs = docs
        print(f"[BM25] Index built over {len(docs)} documents")
    return _bm25, _bm25_docs


# ---------------------------------------------------------------------------
# Hybrid search
# ---------------------------------------------------------------------------

_RRF_K = 60        # standard constant that dampens the impact of high ranks
_BM25_WEIGHT = 2.0 # BM25 contribution multiplier — increase to favour exact keyword matches


def hybrid_search(query: str, k: int = 10) -> list[Document]:
    """Return top-k documents via BM25 + FAISS Reciprocal Rank Fusion.

    Both retrievers fetch fetch_k candidates independently; RRF merges the
    two ranked lists. Course codes appearing in the query score very high
    in BM25 regardless of semantic similarity.
    """
    fetch_k_faiss = min(k * 3, 10)  # semantic recall benefits from wider net
    fetch_k_bm25  = min(k * 2, 10)  # keyword match is precise, 20 is sufficient

    vs = get_vectorstore()
    bm25, bm25_docs = _get_bm25()

    # --- FAISS: semantic search ---
    faiss_results: list[tuple[Document, float]] = vs.similarity_search_with_score(query, k=fetch_k_faiss)
    faiss_results.sort(key=lambda x: x[1])  # ascending L2 distance → most similar first

    # --- BM25: keyword search ---
    tokens = _tokenize(query)
    bm25_scores = bm25.get_scores(tokens)
    bm25_ranked_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:fetch_k_bm25]

    # --- RRF fusion ---
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, (doc, _) in enumerate(faiss_results):
        key = doc.metadata["course_code"]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        doc_map[key] = doc

    for rank, idx in enumerate(bm25_ranked_indices):
        doc = bm25_docs[idx]
        key = doc.metadata["course_code"]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + _BM25_WEIGHT / (_RRF_K + rank + 1)
        if key not in doc_map:
            doc_map[key] = doc

    # --- Sort and annotate ---
    top_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:k]
    results: list[Document] = []
    for key in top_keys:
        doc = doc_map[key]
        doc.metadata["rrf_score"] = round(rrf_scores[key], 6)
        results.append(doc)

    return results
