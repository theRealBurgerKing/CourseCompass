"""Query parsing: turn the raw (possibly Chinese, possibly follow-up) message into a structured retrieval request.

Runs on every turn (not just multi-turn) because the corpus is English while users ask in Chinese:
  - english_query   → keywords for BM25 (BM25 can't tokenise Chinese) and the semantic query
  - standalone_question → the question with pronouns/ellipsis resolved from history, in the user's language
  - course_codes    → codes to fetch directly instead of hoping retrieval ranks them
  - terms           → hard filter on offering terms
  - intent          → how many courses to hand to the LLM
"""
import os
import re
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

COURSE_CODE_RE = re.compile(r"\b[A-Za-z]{4}\d{4}\b")
VALID_TERMS = {"Term 1", "Term 2", "Term 3", "Summer Term"}


class ParsedQuery(BaseModel):
    standalone_question: str = Field(
        description="把用户最新问题结合对话历史改写成不依赖上下文的完整问题，保持用户原语言；"
        "把“它/那门课/其中”等指代换成具体课程代码或主题"
    )
    english_query: str = Field(
        description="用于检索英文课程库的英文关键词句（不是翻译整句），包含主题的常见英文术语，"
        "如“machine learning deep learning neural networks”；若问题只是询问某门课代码，可只写课程代码"
    )
    course_codes: list[str] = Field(
        default_factory=list,
        description="问题中明确提到、或由历史指代可确定的课程代码（如 COMP9417），没有则为空",
    )
    terms: list[str] = Field(
        default_factory=list,
        description="用户明确要求的开课学期，只能取 Term 1 / Term 2 / Term 3 / Summer Term；未提及则为空",
    )
    intent: Literal["lookup", "compare", "recommend", "other"] = Field(
        description="lookup=询问某一门具体课程；compare=对比多门课；recommend=按主题/目标推荐或列举课程；other=其他"
    )


_SYSTEM = """你是 UNSW 研究生选课系统的查询解析器。把用户最新一条消息解析成结构化检索请求。
- 课程库是英文的，english_query 必须是英文检索关键词。
- 只提取用户明确提到的课程代码和学期，不要猜测。
- 课程代码是 4 个字母加 4 个数字，统一大写。
- 对话历史只用于消解指代，不要把历史里无关的内容带进 english_query。"""

_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

_parser_chain = None


def _get_chain():
    global _parser_chain
    if _parser_chain is None:
        model = os.getenv("OPENAI_PARSER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.6-sol"
        _parser_chain = _prompt | ChatOpenAI(model=model, temperature=0).with_structured_output(ParsedQuery)
    return _parser_chain


def _normalise(p: ParsedQuery, message: str) -> ParsedQuery:
    """Clean the LLM output and union in codes found by regex so a code is never dropped."""
    codes: list[str] = []
    for c in [*p.course_codes, *COURSE_CODE_RE.findall(message)]:
        c = c.upper()
        if COURSE_CODE_RE.fullmatch(c) and c not in codes:
            codes.append(c)
    p.course_codes = codes
    p.terms = [t for t in p.terms if t in VALID_TERMS]
    return p


def parse_query(message: str, history: list[BaseMessage]) -> ParsedQuery:
    """Parse the query; on any LLM failure fall back to using the raw message."""
    try:
        parsed = _get_chain().invoke({"input": message, "chat_history": history})
        if parsed is None:
            raise ValueError("empty parser output")
        return _normalise(parsed, message)
    except Exception as exc:  # retrieval must still work if the parser call fails
        print(f"[QueryParser] fallback to raw message: {exc}")
        return _normalise(
            ParsedQuery(standalone_question=message, english_query=message, intent="other"),
            message,
        )
