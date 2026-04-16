import type { CourseSource } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function streamMessage(
  message: string,
  sessionId: string,
  onToken: (token: string) => void,
  onSources: (sources: CourseSource[]) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })

  if (!res.ok || !res.body) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      message = body.detail ?? body.message ?? message
    } catch {
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        message = 'Backend unreachable — is the FastAPI server running on port 8000?'
      }
    }
    throw new Error(message)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Split on \n to get individual lines; keep any trailing incomplete line in buffer
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const rawLine of lines) {
      const line = rawLine.trimEnd()       // strip trailing \r from CRLF
      if (!line.startsWith('data: ')) continue

      const data = line.slice(6)           // strip the "data: " prefix
      if (data === '[DONE]') return

      const event = JSON.parse(data)       // complete line → always valid JSON
      if (event.type === 'token') {
        onToken(event.content as string)
      } else if (event.type === 'sources') {
        onSources(event.sources as CourseSource[])
      } else if (event.type === 'error') {
        throw new Error(event.content as string)
      }
    }
  }
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/chat/${sessionId}`, { method: 'DELETE' })
}
