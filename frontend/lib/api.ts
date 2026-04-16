import type { CourseSource } from '@/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type HistoryItem = { role: 'user' | 'assistant'; content: string }

export async function streamMessage(
  message: string,
  conversationId: string,
  history: HistoryItem[],
  accessToken: string,
  onToken: (token: string) => void,
  onSources: (sources: CourseSource[]) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
    },
    body: JSON.stringify({ message, conversation_id: conversationId, history }),
  })

  if (!res.ok || !res.body) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body.detail ?? body.message ?? msg
    } catch {
      if ([502, 503, 504].includes(res.status))
        msg = 'Backend unreachable — is the FastAPI server running on port 8000?'
    }
    throw new Error(msg)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const rawLine of lines) {
      const line = rawLine.trimEnd()
      if (!line.startsWith('data: ')) continue

      const data = line.slice(6)
      if (data === '[DONE]') return

      const event = JSON.parse(data)
      if (event.type === 'token')   onToken(event.content as string)
      else if (event.type === 'sources') onSources(event.sources as CourseSource[])
      else if (event.type === 'error')   throw new Error(event.content as string)
    }
  }
}
