"""RAG chain with streaming support — compatible with LangChain 1.x.

Flow per request:
  1. If history exists → condense (question + history) → standalone question
  2. FAISS retrieves top-5 relevant courses
  3. LLM streams answer token by token via astream()
  4. Yields SSE-style dicts: {"type":"token","content":"..."} then {"type":"sources",...}
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from .vectorstore import get_vectorstore
from typing import AsyncGenerator, Dict, List

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CONTEXTUALIZE_Q_SYSTEM = (
    "Given a chat history and the latest user question which might reference "
    "context in the chat history, formulate a standalone question that can be "
    "understood without the chat history. "
    "Do NOT answer the question — just reformulate it if needed, otherwise return it as-is."
)

_QA_SYSTEM_PREFIX = """You are CourseCompass, an AI course selection advisor for UNSW \
(University of New South Wales). Help students choose courses that match their \
interests, background, and study goals.

Guidelines:
- Always cite specific course codes (e.g. COMP9020)
- Mention offering terms and faculty when relevant
- Compare courses objectively when asked
- Only reference courses present in the context below
- If a requested course is not in the context, say so honestly

Retrieved course context:
"""

# ---------------------------------------------------------------------------
# In-memory session store  (session_id → list[BaseMessage])
# ---------------------------------------------------------------------------

_sessions: Dict[str, List[BaseMessage]] = {}


def get_history(session_id: str) -> List[BaseMessage]:
    return _sessions.get(session_id, [])


def _append_history(session_id: str, human: str, ai: str) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].extend([HumanMessage(content=human), AIMessage(content=ai)])
    _sessions[session_id] = _sessions[session_id][-20:]


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# LLM singleton
# ---------------------------------------------------------------------------

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.3, streaming=True)
    return _llm


# ---------------------------------------------------------------------------
# Public streaming query
# ---------------------------------------------------------------------------

async def stream_query(
    message: str, session_id: str
) -> AsyncGenerator[dict, None]:
    """Async generator that yields SSE event dicts.

    Event shapes:
      {"type": "token",   "content": "<chunk>"}   — one per streamed token
      {"type": "sources", "sources": [...]}        — emitted once after streaming
      {"type": "error",   "content": "<msg>"}      — emitted on failure
    """
    llm = _get_llm()
    retriever = get_vectorstore().as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )
    history = get_history(session_id)

    try:
        # Step 1 — condense only when there is prior history
        standalone_question = message
        if history:
            condense_prompt = ChatPromptTemplate.from_messages([
                ("system", _CONTEXTUALIZE_Q_SYSTEM),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ])
            condense_chain = condense_prompt | llm | StrOutputParser()
            standalone_question = condense_chain.invoke(
                {"input": message, "chat_history": history}
            )

        # Step 2 — retrieve relevant course docs
        docs: List[Document] = retriever.invoke(standalone_question)
        context = "\n\n---\n\n".join(d.page_content for d in docs)

        # Step 3 — build messages and stream answer
        messages: List[BaseMessage] = [
            SystemMessage(content=_QA_SYSTEM_PREFIX + context),
            *history,
            HumanMessage(content=message),
        ]

        full_answer = ""
        async for chunk in llm.astream(messages):
            token: str = chunk.content
            if token:
                full_answer += token
                yield {"type": "token", "content": token}

        # Step 4 — persist to session history
        _append_history(session_id, message, full_answer)

        # Step 5 — emit source metadata
        yield {
            "type": "sources",
            "sources": [doc.metadata for doc in docs],
        }

    except Exception as exc:
        yield {"type": "error", "content": str(exc)}
