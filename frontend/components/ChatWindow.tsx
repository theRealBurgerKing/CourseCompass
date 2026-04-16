'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { Message, Conversation, CourseSource } from '@/types'
import type { HistoryItem } from '@/lib/api'
import { streamMessage } from '@/lib/api'
import { createClient } from '@/lib/supabase'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import Sidebar from './Sidebar'
import SettingsModal from './SettingsModal'

// Sentinel id — marks a conversation whose messages haven't loaded yet
const LOADING_ID = '__loading__'
const LOADING_MSG: Message = { id: LOADING_ID, role: 'assistant', content: '' }

const EXAMPLE_QUESTIONS = [
  '介绍 COMP9021',
  '比较 COMP6080 和 COMP9020 的难度',
  '如果我想学前端，应该选哪门课？',
]

export default function ChatWindow() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string>('')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isInitializing, setIsInitializing] = useState(true)
  const [userEmail, setUserEmail] = useState<string>('')
  const [avatarUrl, setAvatarUrl] = useState<string>('')
  const [userId, setUserId] = useState<string>('')
  const [showSettings, setShowSettings] = useState(false)
  const accessTokenRef = useRef<string>('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const activeConv = conversations.find((c) => c.id === activeId)
  const allMessages = activeConv?.messages ?? [LOADING_MSG]
  const messages = allMessages.filter((m) => m.id !== LOADING_ID)
  const isConvLoading = allMessages.some((m) => m.id === LOADING_ID)

  // ── Load conversations + user on mount ──────────────────────────────────
  useEffect(() => {
    const init = async () => {
      const supabase = createClient()

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
      const uid = user?.id ?? ''
      setUserId(uid)

      // Prefer custom uploaded avatar from Storage over OAuth metadata avatar
      if (uid) {
        const { data: files } = await supabase.storage.from('avatars').list(uid)
        const avatarFile = files?.find((f) => f.name.startsWith('avatar'))
        if (avatarFile) {
          const { data } = supabase.storage.from('avatars').getPublicUrl(`${uid}/${avatarFile.name}`)
          setAvatarUrl(`${data.publicUrl}?t=${avatarFile.updated_at}`)
        } else {
          setAvatarUrl(user?.user_metadata?.avatar_url ?? '')
        }
      }

      const { data: convRows } = await supabase
        .from('conversations')
        .select('id, title')
        .order('updated_at', { ascending: false })

      if (convRows && convRows.length > 0) {
        const convs: Conversation[] = convRows.map((r) => ({
          id: r.id,
          title: r.title,
          messages: [LOADING_MSG],
        }))
        setConversations(convs)
        setActiveId(convs[0].id)
        await loadMessages(convs[0].id, convs)
      } else {
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

    const msgs: Message[] = (data ?? []).map((m) => ({
      id: m.id as string,
      role: m.role as 'user' | 'assistant',
      content: m.content as string,
      sources: (m.sources as CourseSource[]) ?? [],
    }))

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

    const conv: Conversation = { id: data.id, title: data.title, messages: [] }
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    setInput('')
    return conv.id
  }

  // ── Core send logic ───────────────────────────────────────────────────────

  const sendMessage = useCallback(async (text: string) => {
    if (!text || isLoading) return

    const convId = activeId
    const userMsgId = crypto.randomUUID()
    const placeholderId = crypto.randomUUID()

    const userMsg: Message = { id: userMsgId, role: 'user', content: text }
    const placeholder: Message = { id: placeholderId, role: 'assistant', content: '' }

    const currentMsgs = activeConv?.messages ?? []
    const history: HistoryItem[] = currentMsgs
      .filter((m) => m.id !== LOADING_ID && m.content !== '')
      .map((m) => ({ role: m.role, content: m.content }))

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
  }, [isLoading, activeId, activeConv])

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    const text = input.trim()
    if (!text) return
    setInput('')
    await sendMessage(text)
  }, [input, sendMessage])

  const handleExampleClick = useCallback(async (question: string) => {
    await sendMessage(question)
  }, [sendMessage])

  const handleNewChat = async () => {
    if (isLoading) return
    await createConversation()
  }

  const handleSelectConv = async (id: string) => {
    if (isLoading || id === activeId) return
    setActiveId(id)
    const conv = conversations.find((c) => c.id === id)
    if (conv && conv.messages.length === 0) {
      await loadMessages(id)
    }
  }

  const handleDeleteConv = async (id: string) => {
    const supabase = createClient()
    await supabase.from('conversations').delete().eq('id', id)

    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (id === activeId) {
        if (next.length > 0) {
          setActiveId(next[0].id)
          loadMessages(next[0].id, next)
        } else {
          createConversation()
        }
      }
      return next
    })
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
        avatarUrl={avatarUrl}
        onSelect={handleSelectConv}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConv}
        onSignOut={handleSignOut}
        onOpenSettings={() => setShowSettings(true)}
        disabled={isLoading}
      />

      {showSettings && (
        <SettingsModal
          userEmail={userEmail}
          avatarUrl={avatarUrl}
          userId={userId}
          conversations={conversations}
          onClose={() => setShowSettings(false)}
          onSignOut={handleSignOut}
          onAvatarChange={(url) => setAvatarUrl(url)}
        />
      )}

      <div className="flex flex-1 flex-col overflow-hidden bg-gray-50">
        {/* Header */}
        <div className="flex items-center border-b border-gray-200 bg-white px-6 py-3.5 shadow-sm">
          <h1 className="flex-1 truncate text-sm font-semibold text-gray-700">
            {activeConv?.title ?? 'New conversation'}
          </h1>
          <a
            href="/doc"
            target="_blank"
            rel="noopener noreferrer"
            title="相关资料"
            className="ml-3 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </a>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-2xl space-y-5">

            {/* Loading state */}
            {isConvLoading && (
              <div className="flex justify-center pt-20 text-gray-300">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-indigo-400" />
              </div>
            )}

            {/* Welcome screen — shown when conversation is empty */}
            {!isConvLoading && messages.length === 0 && (
              <div className="flex flex-col items-center pt-24 text-center">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FFD100] text-lg font-bold text-gray-900 shadow">
                  CC
                </div>
                <h2 className="text-xl font-semibold text-gray-800">有什么可以帮你的？</h2>
                <p className="mt-1.5 text-sm text-gray-400">UNSW 选课顾问 · 2026 年课程</p>

                <div className="mt-8 w-full max-w-md space-y-2.5">
                  {EXAMPLE_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => handleExampleClick(q)}
                      disabled={isLoading}
                      className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-600 shadow-sm transition-all hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 hover:shadow-md disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} avatarUrl={avatarUrl} userEmail={userEmail} />
            ))}

            <div ref={bottomRef} />
          </div>
        </div>

        <div className="px-4 py-4">
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
