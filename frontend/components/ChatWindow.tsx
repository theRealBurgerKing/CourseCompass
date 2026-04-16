'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { Message, Conversation, CourseSource } from '@/types'
import type { HistoryItem } from '@/lib/api'
import { streamMessage } from '@/lib/api'
import { createClient } from '@/lib/supabase'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import Sidebar from './Sidebar'

// Welcome message is UI-only — never persisted to Supabase
const WELCOME: Message = {
  id: '__welcome__',
  role: 'assistant',
  content:
    "Hi! I'm **CourseCompass**, your UNSW course selection advisor.\n\nAsk me anything — course recommendations, comparisons, term schedules, or what to study for a specific goal.",
  sources: [],
}

export default function ChatWindow() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string>('')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [userEmail, setUserEmail] = useState<string>('')
  const accessTokenRef = useRef<string>('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const activeConv = conversations.find((c) => c.id === activeId)
  const messages = activeConv?.messages ?? [WELCOME]

  // ── Load conversations + user on mount ──────────────────────────────────
  useEffect(() => {
    const init = async () => {
      const supabase = createClient()

      // Get session token — onAuthStateChange keeps it fresh for the lifetime of the page
      let { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        const { data } = await supabase.auth.refreshSession()
        session = data.session
      }
      accessTokenRef.current = session?.access_token ?? ''

      supabase.auth.onAuthStateChange((_event, newSession) => {
        accessTokenRef.current = newSession?.access_token ?? ''
      })

      const { data: { user } } = await supabase.auth.getUser()
      setUserEmail(user?.email ?? '')

      const { data: convRows } = await supabase
        .from('conversations')
        .select('id, title')
        .order('updated_at', { ascending: false })

      if (convRows && convRows.length > 0) {
        const convs: Conversation[] = convRows.map((r) => ({
          id: r.id,
          title: r.title,
          messages: [WELCOME],           // placeholder until messages load
        }))
        setConversations(convs)
        setActiveId(convs[0].id)
        await loadMessages(convs[0].id, convs)
      } else {
        // First-time user — create an initial conversation
        await createConversation()
      }

      setIsInitializing(false)
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Supabase helpers ─────────────────────────────────────────────────────

  const loadMessages = async (convId: string, baseConvs?: Conversation[]) => {
    const supabase = createClient()
    const { data } = await supabase
      .from('messages')
      .select('id, role, content, sources')
      .eq('conversation_id', convId)
      .order('created_at', { ascending: true })

    const msgs: Message[] = [
      WELCOME,
      ...(data ?? []).map((m) => ({
        id: m.id as string,
        role: m.role as 'user' | 'assistant',
        content: m.content as string,
        sources: (m.sources as CourseSource[]) ?? [],
      })),
    ]

    setConversations((prev) =>
      (baseConvs ?? prev).map((c) => (c.id === convId ? { ...c, messages: msgs } : c)),
    )
  }

  const createConversation = async (): Promise<string | null> => {
    const supabase = createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return null
    const { data, error } = await supabase
      .from('conversations')
      .insert({ title: 'New conversation', user_id: user.id })
      .select('id, title')
      .single()

    if (error || !data) return null

    const conv: Conversation = { id: data.id, title: data.title, messages: [WELCOME] }
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    setInput('')
    return conv.id
  }

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text || isLoading) return

    const convId = activeId
    const userMsgId = crypto.randomUUID()
    const placeholderId = crypto.randomUUID()

    const userMsg: Message = { id: userMsgId, role: 'user', content: text }
    const placeholder: Message = { id: placeholderId, role: 'assistant', content: '' }

    // Build history from persisted messages (exclude welcome + placeholder)
    const currentMsgs = activeConv?.messages ?? []
    const history: HistoryItem[] = currentMsgs
      .filter((m) => m.id !== '__welcome__' && m.content !== '')
      .map((m) => ({ role: m.role, content: m.content }))

    // Optimistic UI update
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== convId) return c
        const isFirst = !c.messages.some((m) => m.role === 'user')
        return {
          ...c,
          title: isFirst ? (text.length > 40 ? text.slice(0, 40) + '…' : text) : c.title,
          messages: [...c.messages, userMsg, placeholder],
        }
      }),
    )
    setInput('')
    setIsLoading(true)

    const accumulator = { answer: '', sources: [] as CourseSource[] }

    try {
      await streamMessage(
        text,
        convId,
        history,
        accessTokenRef.current,
        (token) => {
          accumulator.answer += token
          setConversations((prev) =>
            prev.map((c) =>
              c.id !== convId ? c : {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === placeholderId ? { ...m, content: m.content + token } : m,
                ),
              },
            ),
          )
        },
        (sources) => {
          accumulator.sources = sources
          setConversations((prev) =>
            prev.map((c) =>
              c.id !== convId ? c : {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === placeholderId ? { ...m, sources } : m,
                ),
              },
            ),
          )
        },
      )

      // Persist to Supabase
      const supabase = createClient()
      const isFirst = !history.some((h) => h.role === 'user')

      await supabase.from('messages').insert([
        { id: userMsgId, conversation_id: convId, role: 'user', content: text, sources: [] },
        { id: placeholderId, conversation_id: convId, role: 'assistant', content: accumulator.answer, sources: accumulator.sources },
      ])

      if (isFirst) {
        const title = text.length > 40 ? text.slice(0, 40) + '…' : text
        await supabase.from('conversations').update({ title, updated_at: new Date().toISOString() }).eq('id', convId)
      } else {
        await supabase.from('conversations').update({ updated_at: new Date().toISOString() }).eq('id', convId)
      }

    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Something went wrong.'
      setConversations((prev) =>
        prev.map((c) =>
          c.id !== convId ? c : {
            ...c,
            messages: c.messages.map((m) =>
              m.id === placeholderId ? {
                ...m,
                content: `Sorry, I encountered an error: **${errMsg}**`,
                sources: [],
              } : m,
            ),
          },
        ),
      )
    } finally {
      setIsLoading(false)
    }
  }, [input, isLoading, activeId, activeConv])

  const handleNewChat = async () => {
    if (isLoading) return
    await createConversation()
  }

  const handleSelectConv = async (id: string) => {
    if (isLoading || id === activeId) return
    setActiveId(id)

    // Load messages if not already loaded (only WELCOME present)
    const conv = conversations.find((c) => c.id === id)
    if (conv && conv.messages.length <= 1) {
      await loadMessages(id)
    }
  }

  const handleSignOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    window.location.href = '/auth'
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (isInitializing) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3 text-gray-400">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-indigo-500" />
          <p className="text-sm">Loading…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        userEmail={userEmail}
        onSelect={handleSelectConv}
        onNewChat={handleNewChat}
        onSignOut={handleSignOut}
        disabled={isLoading}
      />

      <div className="flex flex-1 flex-col overflow-hidden bg-gray-50">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-2xl space-y-5">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

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
    </div>
  )
}
