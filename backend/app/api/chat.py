import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas import ChatRequest
from app.rag.chain import stream_query, clear_session

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    """Stream the AI answer as Server-Sent Events (SSE).

    Event types sent to the client:
      data: {"type":"token",   "content":"<chunk>"}
      data: {"type":"sources", "sources":[...]}
      data: {"type":"error",   "content":"<msg>"}
      data: [DONE]
    """
    async def event_stream():
        async for event in stream_query(request.message, request.session_id):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering if proxied
        },
    )


@router.delete("/chat/{session_id}")
async def clear_chat(session_id: str):
    """Clear conversation history for a given session."""
    clear_session(session_id)
    return {"message": f"Session '{session_id}' cleared."}
