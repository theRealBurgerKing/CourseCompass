"""Deterministic retrieval / constraint metrics. No LLM, no network.

Ground truth per case (see cases.json):
  must        core courses — missing one is a miss
  acceptable  also-relevant courses — fine to return, not required
  relevant    = must ∪ acceptable

`returned` is the ordered list of course codes actually handed to the LLM (k = len(returned)).
A metric returns None when it does not apply to the case, and None values are skipped when averaging.
"""
import re
from collections import defaultdict

COURSE_CODE_RE = re.compile(r"\b[A-Z]{4}\d{4}\b")


def recall(returned: list[str], must: list[str]) -> float | None:
    """Share of must-courses that were returned."""
    if not must:
        return None
    return len(set(returned) & set(must)) / len(set(must))


def precision(returned: list[str], relevant: list[str]) -> float | None:
    """Share of returned courses that are relevant (must or acceptable)."""
    if not returned:
        return None
    return len(set(returned) & set(relevant)) / len(returned)


def precision_ceiling(returned: list[str], relevant: list[str]) -> float | None:
    """Best achievable precision for this k: with few relevant courses a large k caps precision."""
    if not returned:
        return None
    return min(len(set(relevant)), len(returned)) / len(returned)


def reciprocal_rank(returned: list[str], must: list[str]) -> float | None:
    """1 / rank of the first must-course (0 if none returned)."""
    if not must:
        return None
    for rank, code in enumerate(returned, start=1):
        if code in must:
            return 1.0 / rank
    return 0.0


def term_compliance(codes: list[str], terms: list[str], course_terms: dict[str, set[str]]) -> float | None:
    """Share of `codes` that run in at least one of the requested terms.

    A course with no listed terms cannot be confirmed for a term, so it counts as a violation.
    """
    if not terms or not codes:
        return None
    wanted = set(terms)
    return sum(bool(course_terms.get(c, set()) & wanted) for c in codes) / len(codes)


def code_presence(returned: list[str], explicit_codes: list[str], corpus_codes: set[str]) -> float | None:
    """Share of the user's explicitly named (and existing) course codes that were returned."""
    named = [c for c in explicit_codes if c in corpus_codes]
    if not named:
        return None
    return len(set(returned) & set(named)) / len(named)


def _answer_codes(answer: str, course_terms: dict[str, set[str]], skip: list[str] | None) -> list[str]:
    skipped = set(skip or [])
    return [c for c in dict.fromkeys(COURSE_CODE_RE.findall(answer)) if c in course_terms and c not in skipped]


def answer_term_compliance(answer: str, terms: list[str], course_terms: dict[str, set[str]],
                           explicit_codes: list[str] | None = None,
                           context_codes: list[str] | None = None) -> float | None:
    """Term compliance of the course codes recommended in the *answer text*.

    Skipped, because they are not recommendations:
      - codes the user typed ("COMP9242 runs in Term 3, not Term 2" is a correct answer)
      - codes outside the retrieved context (e.g. the model retracting an earlier turn's suggestion);
        those are reported by out_of_context_rate instead
    """
    if not terms:
        return None
    codes = _answer_codes(answer, course_terms, explicit_codes)
    if context_codes is not None:
        codes = [c for c in codes if c in set(context_codes)]
    return term_compliance(codes, terms, course_terms)


def out_of_context_rate(answer: str, context: str, course_terms: dict[str, set[str]],
                        explicit_codes: list[str] | None = None) -> float | None:
    """Share of course codes in the answer that appear nowhere in the context text the LLM was given.

    A code mentioned inside a retrieved course's own text (an equivalent course, a prerequisite)
    is grounded, so it is not counted. Diagnostic only.
    """
    codes = _answer_codes(answer, course_terms, explicit_codes)
    if not codes:
        return None
    in_context = set(COURSE_CODE_RE.findall(context))
    return sum(c not in in_context for c in codes) / len(codes)


def mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def summarize(rows: list[dict], metric_keys: list[str]) -> dict[str, dict[str, float | None]]:
    """Average each metric overall and per category: {"ALL": {...}, "topic": {...}, ...}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups["ALL"].append(r)
        groups[r["category"]].append(r)
    return {g: {k: mean([r.get(k) for r in rs]) for k in metric_keys} for g, rs in groups.items()}


# ---------------------------------------------------------------------------
# Case validation — catches labelling mistakes before they silently skew metrics
# ---------------------------------------------------------------------------

_TERM_POINT_RE = re.compile(r"^([A-Z]{4}\d{4}) 在 (.+) 开设$")
CATEGORIES = {"topic", "code_lookup", "compare", "detail", "term_filter", "multi_turn"}


def validate_cases(cases: list[dict], courses: list[dict]) -> list[str]:
    """Return a list of problems (empty = cases are consistent with the course data)."""
    by_code = {c["course_code"]: c for c in courses}
    terms_of = {code: {t.strip() for t in c["offering_terms"].split(",") if t.strip()} for code, c in by_code.items()}
    errs: list[str] = []
    seen: set[str] = set()
    for c in cases:
        cid = c.get("id", "?")
        if cid in seen:
            errs.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("category") not in CATEGORIES:
            errs.append(f"{cid}: bad category {c.get('category')!r}")
        if not c.get("must"):
            errs.append(f"{cid}: must is empty")
        for field in ("must", "acceptable"):
            for code in c.get(field, []):
                if code not in by_code:
                    errs.append(f"{cid}: {field} code {code} not in corpus")
        if set(c.get("must", [])) & set(c.get("acceptable", [])):
            errs.append(f"{cid}: must and acceptable overlap")
        wanted = set(c["constraints"].get("terms", []))
        if wanted:
            for code in [*c.get("must", []), *c.get("acceptable", [])]:
                if code in terms_of and not (terms_of[code] & wanted):
                    errs.append(f"{cid}: {code} does not run in {sorted(wanted)} (has {sorted(terms_of[code]) or 'no terms'})")
        for kp in c.get("key_points", []):
            m = _TERM_POINT_RE.match(kp)
            if m and m.group(1) in by_code and by_code[m.group(1)]["offering_terms"] != m.group(2):
                errs.append(f"{cid}: key point {kp!r} != data {by_code[m.group(1)]['offering_terms']!r}")
        for code in c["constraints"].get("codes", []):
            if not COURSE_CODE_RE.fullmatch(code):
                errs.append(f"{cid}: malformed constraint code {code}")
        for role, text in c.get("history", []):
            if role not in ("user", "assistant"):
                errs.append(f"{cid}: bad history role {role!r}")
    return errs
