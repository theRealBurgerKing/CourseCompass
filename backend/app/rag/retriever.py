"""Hybrid retriever: BM25 (keyword) + FAISS (semantic) fused with Reciprocal Rank Fusion.

BM25 gives exact keyword / course-code matches; FAISS captures semantic similarity.
RRF combines both rankings without needing score normalisation. On top of that:
  - an optional offering-term hard filter is applied to both retrievers
  - directly requested course codes are pinned to the front, outside the ranking
"""
import re
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from .vectorstore import get_vectorstore
from .loader import load_course_documents, parse_terms

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
_BM25_WEIGHT = 1.0 # BM25 contribution multiplier; the query is now English keywords so no extra boost needed
_POOL = 20         # candidates fetched from each retriever before fusion


def _matches_terms(doc: Document, terms: set[str]) -> bool:
    """Courses with no listed terms can't be confirmed for a requested term, so they are excluded."""
    return bool(parse_terms(doc.metadata.get("offering_terms", "")) & terms)


def hybrid_search(
    bm25_query: str,
    semantic_query: str,
    k: int = 6,
    terms: list[str] | None = None,
    pinned_codes: list[str] | None = None,
    explicit_codes: list[str] | None = None,
) -> list[Document]:
    """Return up to k documents (pinned codes first, then BM25 + FAISS fused by RRF).

    pinned_codes are always returned (even beyond k). When a term filter is active, a pinned code
    that doesn't run in that term is dropped unless the user typed it (explicit_codes) — codes
    resolved from chat history ("其中 Term 2 能上的") must still respect the filter.
    """
    term_set = set(terms or [])
    vs = get_vectorstore()
    bm25, bm25_docs = _get_bm25()

    # --- FAISS: semantic search (filter applied inside the index scan) ---
    flt = (lambda md: bool(parse_terms(md.get("offering_terms", "")) & term_set)) if term_set else None
    faiss_results: list[tuple[Document, float]] = vs.similarity_search_with_score(
        semantic_query, k=_POOL, fetch_k=len(bm25_docs), filter=flt
    )
    faiss_results.sort(key=lambda x: x[1])  # ascending L2 distance → most similar first

    # --- BM25: keyword search ---
    tokens = _tokenize(bm25_query)
    bm25_scores = bm25.get_scores(tokens) if tokens else [0.0] * len(bm25_docs)
    bm25_ranked = [
        i for i in sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
        if bm25_scores[i] > 0  # zero score = no keyword overlap; ranking those is pure noise
        and (not term_set or _matches_terms(bm25_docs[i], term_set))
    ][:_POOL]

    # --- RRF fusion ---
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, (doc, _) in enumerate(faiss_results):
        key = doc.metadata["course_code"]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        doc_map[key] = doc

    for rank, idx in enumerate(bm25_ranked):
        doc = bm25_docs[idx]
        key = doc.metadata["course_code"]
        rrf_scores[key] = rrf_scores.get(key, 0.0) + _BM25_WEIGHT / (_RRF_K + rank + 1)
        doc_map.setdefault(key, doc)

    # --- Pin requested codes, then fill remaining slots by RRF score ---
    all_docs = {d.metadata["course_code"]: d for d in bm25_docs}
    explicit = set(explicit_codes or [])
    pinned = [
        c for c in dict.fromkeys(pinned_codes or [])
        if c in all_docs and (not term_set or c in explicit or _matches_terms(all_docs[c], term_set))
    ]

    results: list[Document] = [all_docs[c] for c in pinned]
    for c in pinned:
        all_docs[c].metadata["rrf_score"] = round(rrf_scores.get(c, 0.0), 6)

    for key in sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True):
        if len(results) >= max(k, len(pinned)):
            break
        if key in pinned:
            continue
        doc = doc_map[key]
        doc.metadata["rrf_score"] = round(rrf_scores[key], 6)
        results.append(doc)

    return results
