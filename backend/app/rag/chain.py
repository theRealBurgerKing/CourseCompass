"""Stateless RAG chain — history is supplied by the caller each request.

Flow:
  1. Convert history list → LangChain messages
  2. Parse the query (every turn): English retrieval query, course codes, term filter, intent
  3. Hybrid retrieval (BM25 + FAISS, RRF) with term filter; requested course codes are pinned
  4. LLM streams the answer token by token, using the original course text as context
  5. Yields SSE-style dicts
"""
import asyncio
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from .loader import course_texts
from .query_parser import COURSE_CODE_RE, ParsedQuery, parse_query
from .retriever import hybrid_search
from typing import AsyncGenerator, List

_QA_SYSTEM_PREFIX = """你是 CourseCompass，新南威尔士大学（UNSW）的 AI 选课顾问。\
帮助学生根据其兴趣、背景和学习目标选择合适的课程。

回答规范：
- 必须使用中文（简体）输出回答
- 始终引用具体课程代码（如 COMP9020）
- 适时提及开课学期和所属院系
- 被要求时客观地对比课程
- 只引用下方上下文中出现的课程
- 如果所询问的课程不在上下文中，请如实说明

已检索到的课程上下文：
"""

# ---------------------------------------------------------------------------
# LLM singleton
# ---------------------------------------------------------------------------

DEFAULT_CHAT_MODEL = "gpt-5.6-sol"


def _chat_model() -> str:
    return os.getenv("OPENAI_MODEL") or DEFAULT_CHAT_MODEL


_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=_chat_model(), temperature=0.3, streaming=True)
    return _llm


# How many courses to hand the LLM per intent (pinned course codes are always included on top).
_K_BY_INTENT = {"lookup": 3, "compare": 5, "recommend": 8, "other": 6}


def _to_messages(history_items: list) -> List[BaseMessage]:
    """HistoryItem list → LangChain messages (keep last 20 = 10 turns)."""
    return [
        HumanMessage(content=i.content) if i.role == "user" else AIMessage(content=i.content)
        for i in history_items[-20:]
    ]


def retrieve_with_parsed(message: str, parsed: ParsedQuery) -> List[Document]:
    """Retrieve courses for an already-parsed query (blocking)."""
    # BM25 only understands the English keywords + codes; FAISS also sees the user's own wording,
    # which matches the Chinese search aids added to the index.
    return hybrid_search(
        bm25_query=f"{parsed.english_query} {' '.join(parsed.course_codes)}",
        semantic_query=f"{parsed.english_query}\n{parsed.standalone_question}",
        k=_K_BY_INTENT[parsed.intent],
        terms=parsed.terms,
        pinned_codes=parsed.course_codes,
        explicit_codes=[c.upper() for c in COURSE_CODE_RE.findall(message)],
    )


def retrieve_for_query(message: str, history_items: list) -> tuple[ParsedQuery, List[Document]]:
    """Parse the query and retrieve the courses to answer it (blocking; run in a thread from async code)."""
    parsed = parse_query(message, _to_messages(history_items))
    return parsed, retrieve_with_parsed(message, parsed)


def build_context(docs: List[Document]) -> str:
    """The exact text the LLM sees: original course data only (never the generated search aids)."""
    texts = course_texts()
    return "\n\n---\n\n".join(texts[d.metadata["course_code"]] for d in docs)


def build_messages(context: str, history: List[BaseMessage], message: str) -> List[BaseMessage]:
    return [SystemMessage(content=_QA_SYSTEM_PREFIX + context), *history, HumanMessage(content=message)]


def answer_query(message: str, history_items: list) -> dict:
    """Non-streaming end-to-end answer, sharing every step with stream_query (used by the offline eval).

    Returns {"parsed", "docs", "context", "answer"} so metrics can inspect exactly what the LLM saw.
    """
    parsed, docs = retrieve_for_query(message, history_items)
    context = build_context(docs)
    result = _get_llm().invoke(build_messages(context, _to_messages(history_items), message))
    return {"parsed": parsed, "docs": docs, "context": context, "answer": result.text}


# ---------------------------------------------------------------------------
# Public streaming query (stateless)
# ---------------------------------------------------------------------------

async def stream_query(
    message: str,
    history_items: list,        # list of HistoryItem (role + content)
) -> AsyncGenerator[dict, None]:
    """Yield SSE event dicts.

    {"type": "token",   "content": "<chunk>"}
    {"type": "sources", "sources": [...]}
    {"type": "error",   "content": "<msg>"}
    """
    llm = _get_llm()
    history = _to_messages(history_items)

    try:
        # Steps 1-2 — parse the query and retrieve (blocking calls, keep them off the event loop)
        parsed, docs = await asyncio.to_thread(retrieve_for_query, message, history_items)
        context = build_context(docs)

        # Step 3 — stream answer
        async for chunk in llm.astream(build_messages(context, history, message)):
            token: str = chunk.text
            if token:
                yield {"type": "token", "content": token}

        # Step 4 — emit sources
        yield {"type": "sources", "sources": [doc.metadata for doc in docs]}

    except Exception as exc:
        yield {"type": "error", "content": str(exc)}
