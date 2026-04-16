import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.schemas import ChatRequest
from app.rag.chain import stream_query
from app.dependencies import require_auth

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest, _user: dict = Depends(require_auth)):
    """Stream the AI answer as Server-Sent Events (SSE).

    Requires a valid Supabase JWT in the Authorization header.

    SSE event types:
      data: {"type":"token",   "content":"<chunk>"}
      data: {"type":"sources", "sources":[...]}
      data: {"type":"error",   "content":"<msg>"}
      data: [DONE]
    """
    async def event_stream():
        async for event in stream_query(request.message, request.history):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
