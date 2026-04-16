"""RAG chain — compatible with LangChain 1.x (no langchain.chains dependency).

Flow per request:
  1. If history exists → condense (question + history) → standalone question
  2. FAISS retrieves top-5 relevant courses
  3. LLM generates answer using (context + history + question)
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.documents import Document
from .vectorstore import get_vectorstore
from typing import Dict, List, Tuple

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
    # Keep at most 20 messages (10 turns) to stay within context limits
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
        _llm = ChatOpenAI(model="gpt-4.1-nano", temperature=0.3)
    return _llm


# ---------------------------------------------------------------------------
# Public query function
# ---------------------------------------------------------------------------

async def query(message: str, session_id: str) -> Tuple[str, List[Document]]:
    """Run a RAG query and return (answer, source_documents).

    Steps:
      1. Condense question + history into a standalone question (skipped on first turn).
      2. Retrieve top-5 relevant course documents from FAISS.
      3. Build a messages list and call the LLM for the final answer.
    """
    llm = _get_llm()
    retriever = get_vectorstore().as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )
    history = get_history(session_id)

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

    # Step 3 — generate answer
    messages: List[BaseMessage] = [
        SystemMessage(content=_QA_SYSTEM_PREFIX + context),
        *history,
        HumanMessage(content=message),
    ]
    response = llm.invoke(messages)
    answer: str = response.content

    _append_history(session_id, message, answer)
    return answer, docs
