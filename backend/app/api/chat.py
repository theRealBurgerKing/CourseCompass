import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.schemas import ChatRequest
from app.rag.chain import stream_query
from app.rate_limit import rate_limit_chat

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest, _user: dict = Depends(rate_limit_chat)):
    """Stream the AI answer as Server-Sent Events (SSE).

    Requires a valid Supabase JWT in the Authorization header. Limited per user (see app/rate_limit.py):
    HTTP 429 with Retry-After when exceeded; HTTP 422 when the message is empty or too long.

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
