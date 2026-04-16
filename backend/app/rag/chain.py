"""Stateless RAG chain — history is supplied by the caller each request.

Flow:
  1. Convert history list → LangChain messages
  2. If history exists, condense question into a standalone question
  3. FAISS retrieves top-5 relevant courses
  4. LLM streams the answer token by token
  5. Yields SSE-style dicts
"""
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from .retriever import hybrid_search
from typing import AsyncGenerator, List

_CONTEXTUALIZE_Q_SYSTEM = (
    "给定一段对话历史和用户的最新问题（该问题可能引用了对话历史中的内容），"
    "请将其改写为一个无需对话历史即可独立理解的问题。"
    "不要回答该问题——如有必要请重新表述，否则原样返回。"
)

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

_llm: ChatOpenAI | None = None


_condense_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.3, streaming=True)
    return _llm


def _get_condense_llm() -> ChatOpenAI:
    """Separate LLM for question condensation — temperature=0 for deterministic output."""
    global _condense_llm
    if _condense_llm is None:
        _condense_llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0)
    return _condense_llm


_COURSE_CODE_RE = re.compile(r'\b[A-Z]{4}\d{4}\b')


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

    # Convert history dicts → LangChain messages (keep last 20 = 10 turns)
    history: List[BaseMessage] = []
    for item in history_items[-20:]:
        if item.role == "user":
            history.append(HumanMessage(content=item.content))
        else:
            history.append(AIMessage(content=item.content))

    try:
        # Step 1 — condense when history exists
        standalone_question = message
        if history:
            condense_prompt = ChatPromptTemplate.from_messages([
                ("system", _CONTEXTUALIZE_Q_SYSTEM),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ])
            standalone_question = (condense_prompt | _get_condense_llm() | StrOutputParser()).invoke(
                {"input": message, "chat_history": history}
            )
            # Re-inject any course codes from the original message that were dropped during condensation
            original_codes = _COURSE_CODE_RE.findall(message.upper())
            condensed_codes = set(_COURSE_CODE_RE.findall(standalone_question.upper()))
            missing_codes = [c for c in original_codes if c not in condensed_codes]
            if missing_codes:
                standalone_question += " " + " ".join(missing_codes)

        # Step 2 — hybrid retrieve (BM25 + FAISS, fused via RRF)
        docs: List[Document] = hybrid_search(standalone_question, k=4)
        context = "\n\n---\n\n".join(d.page_content for d in docs)

        # Step 3 — stream answer
        messages: List[BaseMessage] = [
            SystemMessage(content=_QA_SYSTEM_PREFIX + context),
            *history,
            HumanMessage(content=message),
        ]
        async for chunk in llm.astream(messages):
            token: str = chunk.content
            if token:
                yield {"type": "token", "content": token}

        # Step 4 — emit sources
        yield {"type": "sources", "sources": [doc.metadata for doc in docs]}

    except Exception as exc:
        yield {"type": "error", "content": str(exc)}
