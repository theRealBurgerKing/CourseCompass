import type { ChatResponse } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function sendMessage(
  message: string,
  sessionId: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.detail ?? body.message ?? message
    } catch {
      // Non-JSON response — likely the backend is down or not reachable
      if (res.status === 502 || res.status === 504 || res.status === 503) {
        message = 'Backend unreachable (502) — is the FastAPI server running on port 8000?'
      } else {
        message = `Server returned HTTP ${res.status} (non-JSON body)`
      }
    }
    throw new Error(message)
  }

  return res.json()
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/chat/${sessionId}`, { method: 'DELETE' })
}
