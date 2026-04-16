"""Stateless RAG chain — history is supplied by the caller each request.

Flow:
  1. Convert history list → LangChain messages
  2. If history exists, condense question into a standalone question
  3. FAISS retrieves top-5 relevant courses
  4. LLM streams the answer token by token
  5. Yields SSE-style dicts
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from .vectorstore import get_vectorstore
from typing import AsyncGenerator, List

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
# LLM singleton
# ---------------------------------------------------------------------------

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.3, streaming=True)
    return _llm


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
    retriever = get_vectorstore().as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )

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
            standalone_question = (condense_prompt | llm | StrOutputParser()).invoke(
                {"input": message, "chat_history": history}
            )

        # Step 2 — retrieve
        docs: List[Document] = retriever.invoke(standalone_question)
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
