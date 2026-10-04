"""Unit tests for the deterministic metrics and the case file. Run from backend/:  python -m eval.test_metrics"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.metrics_retrieval import (
    answer_term_compliance, code_presence, mean, out_of_context_rate, precision, precision_ceiling,
    recall, reciprocal_rank, term_compliance, validate_cases,
)

TERMS = {"A": {"Term 1", "Term 2"}, "B": {"Term 2"}, "C": {"Term 3"}, "D": set()}


def approx(a, b):
    return abs(a - b) < 1e-9


def test_recall():
    assert approx(recall(["A", "B", "X"], ["A", "B", "C", "D"]), 0.5)
    assert recall(["A"], []) is None
    assert approx(recall([], ["A"]), 0.0)


def test_precision_and_ceiling():
    assert approx(precision(["A", "B", "X", "Y"], ["A", "B", "C"]), 0.5)
    assert precision([], ["A"]) is None
    # 1 relevant course but 8 returned -> best possible precision is 1/8
    assert approx(precision_ceiling(list("ABCDEFGH"), ["A"]), 1 / 8)
    assert approx(precision_ceiling(["A", "B"], ["A", "B", "C"]), 1.0)


def test_reciprocal_rank():
    assert approx(reciprocal_rank(["X", "Y", "A"], ["A"]), 1 / 3)
    assert approx(reciprocal_rank(["A", "X"], ["A", "B"]), 1.0)
    assert approx(reciprocal_rank(["X"], ["A"]), 0.0)


def test_term_compliance():
    assert approx(term_compliance(["A", "B"], ["Term 2"], TERMS), 1.0)
    assert approx(term_compliance(["A", "C"], ["Term 2"], TERMS), 0.5)
    assert approx(term_compliance(["D"], ["Term 2"], TERMS), 0.0)   # unknown terms can't be confirmed
    assert term_compliance(["A"], [], TERMS) is None


def test_code_presence_ignores_codes_not_in_corpus():
    assert approx(code_presence(["A", "X"], ["A", "B", "ZZZZ9999"], {"A", "B"}), 0.5)
    assert code_presence(["A"], ["ZZZZ9999"], {"A"}) is None


def test_answer_term_compliance():
    terms = {"COMP1111": {"Term 2"}, "COMP2222": {"Term 3"}}
    assert approx(answer_term_compliance("推荐 COMP1111 和 COMP2222", ["Term 2"], terms), 0.5)
    # a code the user typed themselves is not counted as a recommendation
    assert approx(answer_term_compliance("COMP2222 在 Term 3 开，不是 Term 2；可选 COMP1111", ["Term 2"], terms, ["COMP2222"]), 1.0)
    # a code outside the retrieved context (model retracting an earlier suggestion) is not a recommendation
    assert approx(answer_term_compliance("COMP1111 可选；之前提的 COMP2222 抱歉无法确认", ["Term 2"], terms, None, ["COMP1111"]), 1.0)
    assert answer_term_compliance("没有课程代码", ["Term 2"], terms) is None
    assert answer_term_compliance("COMP1111", [], terms) is None


def test_out_of_context_rate():
    terms = {"COMP1111": {"Term 2"}, "COMP2222": {"Term 3"}, "COMP3333": {"Term 1"}}
    ctx = "Course Code: COMP1111 ... Equivalent Courses: COMP2222"
    assert out_of_context_rate("COMP1111 COMP2222", ctx, terms) == 0.0          # COMP2222 is grounded in the text
    assert approx(out_of_context_rate("COMP1111 COMP3333", ctx, terms), 0.5)    # COMP3333 appears nowhere
    assert out_of_context_rate("COMP3333 是你问的", ctx, terms, ["COMP3333"]) is None  # user-typed code skipped
    assert out_of_context_rate("没有代码", ctx, terms) is None


def test_mean_skips_none():
    assert approx(mean([1.0, None, 0.0]), 0.5)
    assert mean([None]) is None


def test_validate_cases_flags_problems():
    courses = [{"course_code": "COMP1111", "offering_terms": "Term 2"},
               {"course_code": "COMP2222", "offering_terms": "Term 3"}]
    bad = [{"id": "x", "category": "term_filter", "constraints": {"terms": ["Term 2"], "codes": []},
            "must": ["COMP2222"], "acceptable": [], "key_points": ["COMP1111 在 Term 1 开设"], "history": []}]
    problems = " | ".join(validate_cases(bad, courses))
    assert "does not run in" in problems and "key point" in problems


def test_shipped_cases_are_consistent_with_course_data():
    from app.rag.loader import _load_courses
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    problems = validate_cases(cases, _load_courses())
    assert not problems, "\n".join(problems)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok ", name)
    print(f"{len(tests)} tests passed")
