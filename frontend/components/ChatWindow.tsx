'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { Message } from '@/types'
import { streamMessage, clearSession } from '@/lib/api'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'

const WELCOME: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm **CourseCompass**, your UNSW course selection advisor.\n\nAsk me anything — course recommendations, comparisons, term schedules, or what to study for a specific goal.",
  sources: [],
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text || isLoading) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    }
    // Placeholder for the assistant reply (shows typing indicator)
    const placeholderId = crypto.randomUUID()
    const placeholder: Message = {
      id: placeholderId,
      role: 'assistant',
      content: '',
    }

    setMessages((prev) => [...prev, userMsg, placeholder])
    setInput('')
    setIsLoading(true)

    try {
      await streamMessage(
        text,
        sessionId,
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === placeholderId ? { ...m, content: m.content + token } : m,
            ),
          )
        },
        (sources) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === placeholderId ? { ...m, sources } : m,
            ),
          )
        },
      )
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Something went wrong.'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholderId
            ? {
                ...m,
                content: `Sorry, I encountered an error: **${errMsg}**\n\nPlease make sure the backend is running at \`localhost:8000\`.`,
                sources: [],
              }
            : m,
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, sessionId])

  const handleNewChat = async () => {
    await clearSession(sessionId).catch(() => {})
    setMessages([WELCOME])
    setInput('')
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* ── Header ── */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-5 py-3 shadow-sm">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#FFD100] text-sm font-bold text-gray-900 shadow-sm">
            CC
          </div>
          <div>
            <h1 className="text-base font-semibold text-gray-900 leading-none">
              CourseCompass
            </h1>
            <p className="text-[11px] text-gray-400 mt-0.5">UNSW Course Advisor</p>
          </div>
        </div>

        <button
          onClick={handleNewChat}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </header>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-5">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input ── */}
      <div className="border-t border-gray-200 bg-white px-4 py-4">
        <div className="mx-auto max-w-2xl">
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            disabled={isLoading}
          />
          <p className="mt-2 text-center text-[11px] text-gray-400">
            Showing UNSW 2026 courses · Master of Information Technology
          </p>
        </div>
      </div>
    </div>
  )
}
