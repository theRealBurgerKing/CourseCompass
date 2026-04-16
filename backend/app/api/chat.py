from fastapi import APIRouter, HTTPException
from app.schemas import ChatRequest, ChatResponse, CourseSource
from app.rag.chain import query, clear_session

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and receive an AI answer with referenced course sources."""
    try:
        answer, source_docs = await query(request.message, request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Deduplicate sources while preserving retrieval order
    sources: list[CourseSource] = []
    seen: set[str] = set()
    for doc in source_docs:
        code = doc.metadata.get("course_code", "")
        if code and code not in seen:
            seen.add(code)
            sources.append(
                CourseSource(
                    course_code=code,
                    course_name=doc.metadata.get("course_name", ""),
                    units_of_credit=doc.metadata.get("units_of_credit", ""),
                    offering_terms=doc.metadata.get("offering_terms", ""),
                    faculty=doc.metadata.get("faculty", ""),
                )
            )

    return ChatResponse(answer=answer, sources=sources, session_id=request.session_id)


@router.delete("/chat/{session_id}")
async def clear_chat(session_id: str):
    """Clear the conversation history for a given session."""
    clear_session(session_id)
    return {"message": f"Session '{session_id}' cleared."}
