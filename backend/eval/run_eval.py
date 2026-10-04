"""Offline retrieval eval. Run from backend/:  python -m eval.run_eval [--out FILE] [--compare baseline_results.json]

Metrics per case (k = number of docs actually handed to the LLM):
  recall      = |retrieved ∩ expect| / min(|expect|, k)     (capped so list queries aren't unfairly penalised)
  term_prec   = share of retrieved docs whose offering_terms contain the requested term (term cases only)
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from types import SimpleNamespace as NS
from app.rag.loader import load_course_documents

CASES = json.loads((Path(__file__).parent / "retrieval_cases.json").read_text(encoding="utf-8"))
TERMS = {d.metadata["course_code"]: d.metadata.get("offering_terms", "") for d in load_course_documents()}


def retrieve_new(q, history):
    from app.rag.chain import retrieve_for_query
    items = [NS(role=r, content=c) for r, c in history]
    return [d.metadata["course_code"] for d in retrieve_for_query(q, items)[1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", help="earlier results JSON to print mean recall for side by side")
    ap.add_argument("--out")
    a = ap.parse_args()
    fn = retrieve_new

    rows, rsum, r4sum, tsum, tn = [], 0.0, 0.0, 0.0, 0
    for c in CASES:
        got = fn(c["q"], c.get("history", []))
        k = max(len(got), 1)
        rec = len(set(got) & set(c["expect"])) / min(len(c["expect"]), k)
        rec4 = len(set(got[:4]) & set(c["expect"])) / min(len(c["expect"]), 4)
        r4sum += rec4
        row = {"q": c["q"], "got": got, "recall": round(rec, 2), "recall4": round(rec4, 2)}
        if c.get("term"):
            tp = sum(c["term"] in TERMS.get(x, "") for x in got) / k
            row["term_prec"] = round(tp, 2); tsum += tp; tn += 1
        rsum += rec; rows.append(row)
        print(f'{row["recall"]:.2f}  {"T%.2f" % row["term_prec"] if "term_prec" in row else "     "}  {c["q"]}  -> {got}')
    n = len(CASES)
    print(f"\n[current] mean recall = {rsum/n:.3f}, recall@4 = {r4sum/n:.3f} over {n} cases; term precision = {tsum/tn:.3f} over {tn} term cases; avg docs = {sum(len(r['got']) for r in rows)/n:.1f}")
    if a.compare:
        old = json.loads(Path(a.compare).read_text(encoding="utf-8"))
        print(f"[{Path(a.compare).name}] mean recall = {sum(r['recall'] for r in old)/len(old):.3f}, recall@4 = {sum(r.get('recall4', r['recall']) for r in old)/len(old):.3f}")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
