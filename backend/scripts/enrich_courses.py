"""Generate retrieval-only search aids for every course (Chinese summary, bilingual keywords).

Why: courses are English but users ask in Chinese, so embeddings/BM25 alone match poorly.
The aids are appended to the *indexed* text only; the LLM answer context stays the original data.

Run from the backend/ directory, then rebuild the index:
    python -m scripts.enrich_courses
    python -m scripts.build_index
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from app.rag.loader import _load_courses, ENRICHMENT_PATH, render_course_text


class SearchAids(BaseModel):
    summary_zh: str = Field(description="1-2 句简体中文简介，说明这门课学什么，80 字以内")
    keywords_zh: list[str] = Field(description="6-10 个简体中文主题关键词，含常见同义说法")
    keywords_en: list[str] = Field(description="6-10 个英文主题关键词/技术名词")
    suitable_for_zh: str = Field(description="适合什么学习目标或职业方向的学生，40 字以内")


_SYSTEM = (
    "你为 UNSW 研究生课程库生成检索辅助信息，帮助用中文提问的学生找到英文课程。\n"
    "严格只依据给定的课程信息，不要编造先修要求、难度、就业数据或课程中没有的内容。\n"
    "关键词应覆盖学生可能用的说法（例如 机器学习/ML、深度学习/神经网络、网络安全/信息安全）。"
)


def main() -> None:
    model = os.getenv("OPENAI_MODEL") or "gpt-5.6-sol"
    llm = ChatOpenAI(model=model, temperature=0).with_structured_output(SearchAids)

    courses = _load_courses()
    existing = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8")) if ENRICHMENT_PATH.exists() else {}
    todo = [c for c in courses if c["course_code"] not in existing]
    print(f"[Enrich] {len(todo)} to generate, {len(existing)} already done (model={model})")

    inputs = [[("system", _SYSTEM), ("human", render_course_text(c))] for c in todo]
    results = llm.batch(inputs, config={"max_concurrency": 8}, return_exceptions=True)

    failed = []
    for course, res in zip(todo, results):
        if isinstance(res, Exception) or res is None:
            failed.append(course["course_code"])
            continue
        existing[course["course_code"]] = res.model_dump()

    ENRICHMENT_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[Enrich] Saved {len(existing)} entries to {ENRICHMENT_PATH}")
    if failed:
        print(f"[Enrich] FAILED (re-run to retry): {failed}")


if __name__ == "__main__":
    main()
