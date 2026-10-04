"""Offline RAG evaluation. Run from backend/:

    python -m eval.run_eval --retrieval-only [--out FILE] [--compare PREV.json]
    python -m eval.run_eval --full           [--out FILE] [--compare PREV.json]

Retrieval side (deterministic): Recall, Precision (+ its ceiling), MRR, Constraint Compliance
  (term_ok / code_ok / answer_term_ok).
Generation side (--full, LLM judge, needs JUDGE_API_KEY): Faithfulness, Context Recall
  (+ oos_code_rate: share of course codes in the answer that appear nowhere in the context text).

Query-parser output, generated answers and judge verdicts are cached under eval/.cache so a rerun only
pays for what changed. Use --no-cache to recompute everything.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.rag.loader import _load_courses, parse_terms
from eval import metrics_retrieval as M

CASES_PATH = Path(__file__).parent / "cases.json"
CACHE_DIR = Path(__file__).parent / ".cache"

RETRIEVAL_KEYS = ["recall", "precision", "precision_ceiling", "mrr", "term_ok", "code_ok", "avg_docs"]
GENERATION_KEYS = ["answer_term_ok", "oos_code_rate", "faithfulness", "opinion_rate", "context_recall"]


# ---------------------------------------------------------------------------
# Small disk cache (parser output, generated answers)
# ---------------------------------------------------------------------------

def _cache_path(kind: str, *parts) -> Path:
    h = hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return CACHE_DIR / f"{kind}_{h}.json"


def _cache_read(path: Path, use_cache: bool):
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _cache_write(path: Path, value) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# One case
# ---------------------------------------------------------------------------

def evaluate_case(case: dict, full: bool, use_cache: bool, ctx: dict) -> dict:
    from app.rag.chain import _chat_model, _get_llm, _to_messages, build_context, build_messages, retrieve_with_parsed
    from app.rag.query_parser import ParsedQuery, parse_query

    q = case["q"]
    items = [NS(role=r, content=c) for r, c in case.get("history", [])]
    cons = case["constraints"]
    row: dict = {"id": case["id"], "category": case["category"], "q": q}

    # 1. parse (cached) -> retrieve
    parser_model = os.getenv("OPENAI_PARSER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.6-sol"
    p_path = _cache_path("parse", parser_model, q, case.get("history", []))
    cached = _cache_read(p_path, use_cache)
    if cached:
        parsed = ParsedQuery.model_validate(cached)
    else:
        parsed = parse_query(q, _to_messages(items))
        _cache_write(p_path, parsed.model_dump())
    docs = retrieve_with_parsed(q, parsed)
    returned = [d.metadata["course_code"] for d in docs]
    row["parsed"] = {"english_query": parsed.english_query, "course_codes": parsed.course_codes,
                     "terms": parsed.terms, "intent": parsed.intent}
    row["returned"] = returned

    # 2. retrieval metrics
    must, relevant = case["must"], case["must"] + case["acceptable"]
    explicit = cons["codes"]
    trivial_mrr = bool(set(explicit) & set(must))  # a code the user typed is pinned to rank 1
    row.update({
        "recall": M.recall(returned, must),
        "precision": M.precision(returned, relevant),
        "precision_ceiling": M.precision_ceiling(returned, relevant),
        "mrr": None if trivial_mrr else M.reciprocal_rank(returned, must),
        "term_ok": M.term_compliance(returned, cons["terms"], ctx["course_terms"]),
        "code_ok": M.code_presence(returned, explicit, ctx["corpus"]),
        "avg_docs": float(len(returned)),
        "missed": sorted(set(must) - set(returned)),
    })
    if not full:
        return row

    # 3. generate the answer from exactly what retrieval returned (cached)
    from eval import judge
    context = build_context(docs)
    a_path = _cache_path("answer", _chat_model(), context, q, case.get("history", []))
    answer = _cache_read(a_path, use_cache)
    if answer is None:
        answer = _get_llm().invoke(build_messages(context, _to_messages(items), q)).text
        _cache_write(a_path, answer)
    row["answer"] = answer
    row["answer_term_ok"] = M.answer_term_compliance(answer, cons["terms"], ctx["course_terms"], explicit, returned)
    row["oos_code_rate"] = M.out_of_context_rate(answer, context, ctx["course_terms"], explicit)

    # 4. LLM judge
    faith = judge.judge_faithfulness(context, q, answer, use_cache)
    recall = judge.judge_context_recall(context, case["key_points"], use_cache)
    row.update({
        "faithfulness": faith["faithfulness"], "opinion_rate": faith["opinion_rate"],
        "n_facts": faith["n_facts"], "bad_claims": faith["bad_claims"],
        "context_recall": recall["context_recall"], "key_points": recall["points"],
    })
    return row


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt(v) -> str:
    return "  -  " if v is None else f"{v:5.2f}"


def print_table(summary: dict, rows: list[dict], keys: list[str]) -> None:
    order = ["ALL"] + sorted(g for g in summary if g != "ALL")
    counts = {g: sum(1 for r in rows if g == "ALL" or r["category"] == g) for g in order}
    print(f"{'category':<13}{'n':>3}  " + " ".join(f"{k[:11]:>11}" for k in keys))
    for g in order:
        print(f"{g:<13}{counts[g]:>3}  " + " ".join(f"{_fmt(summary[g].get(k)):>11}" for k in keys))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--retrieval-only", action="store_true", help="retrieval + constraint metrics only (no generation / judge)")
    mode.add_argument("--full", action="store_true", help="also generate answers and run the LLM judge")
    ap.add_argument("--cases", default=str(CASES_PATH))
    ap.add_argument("--category", help="only run cases of this category")
    ap.add_argument("--limit", type=int, help="only run the first N cases")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", help="write per-case rows + summary to this JSON file")
    ap.add_argument("--compare", help="earlier --out file; prints the change in each overall metric")
    a = ap.parse_args()

    from eval import judge
    if a.full:
        judge.require_judge_key()

    cases = json.loads(Path(a.cases).read_text(encoding="utf-8"))
    problems = M.validate_cases(cases, _load_courses())
    if problems:
        sys.exit("cases.json is inconsistent with the course data:\n  " + "\n  ".join(problems))
    if a.category:
        cases = [c for c in cases if c["category"] == a.category]
    if a.limit:
        cases = cases[: a.limit]

    courses = _load_courses()
    ctx = {"course_terms": {c["course_code"]: parse_terms(c["offering_terms"]) for c in courses},
           "corpus": {c["course_code"] for c in courses}}

    # warm the singletons once so worker threads don't race to build them
    from app.rag.retriever import _get_bm25
    from app.rag.vectorstore import get_vectorstore
    get_vectorstore(); _get_bm25()

    t0 = time.time()
    def run(case):
        try:
            return evaluate_case(case, a.full, not a.no_cache, ctx)
        except Exception as exc:  # keep going; report the failure on that case
            return {"id": case["id"], "category": case["category"], "q": case["q"], "error": f"{type(exc).__name__}: {exc}"}
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(run, cases))

    errors = [r for r in rows if "error" in r]
    ok = [r for r in rows if "error" not in r]
    if not ok:
        print(f"\nAll {len(errors)} case(s) FAILED:")
        for r in errors:
            print(f"  {r['id']}: {r['error'][:400]}")
        sys.exit(1)
    keys = RETRIEVAL_KEYS + (GENERATION_KEYS if a.full else [])
    summary = M.summarize(ok, keys)

    print(f"\n== Retrieval ({len(ok)} cases, {time.time() - t0:.0f}s) ==")
    print_table(summary, ok, RETRIEVAL_KEYS)
    if a.full:
        print("\n== Generation (LLM judge: %s) ==" % judge.judge_model_name())
        print_table(summary, ok, GENERATION_KEYS)
    low = [r for r in ok if r.get("missed")]
    if low:
        print("\nMissed must-courses:")
        for r in low:
            print(f"  [{r['category']}] {r['q']}  missed={r['missed']}")
    if errors:
        print(f"\n{len(errors)} case(s) FAILED:")
        for r in errors:
            print(f"  {r['id']}: {r['error'][:200]}")

    if a.compare:
        prev = json.loads(Path(a.compare).read_text(encoding="utf-8"))["summary"]["ALL"]
        print(f"\n== Change vs {Path(a.compare).name} (ALL) ==")
        for k in keys:
            old, new = prev.get(k), summary["ALL"].get(k)
            if old is not None and new is not None:
                print(f"  {k:<18}{old:6.3f} -> {new:6.3f}  ({new - old:+.3f})")

    if a.out:
        meta = {"date": time.strftime("%Y-%m-%d %H:%M"), "mode": "full" if a.full else "retrieval-only",
                "n_cases": len(ok), "n_errors": len(errors),
                "chat_model": os.getenv("OPENAI_MODEL"), "parser_model": os.getenv("OPENAI_PARSER_MODEL"),
                "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL"), "judge_model": judge.judge_model_name() if a.full else None}
        Path(a.out).write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nWrote {a.out}")


if __name__ == "__main__":
    main()
