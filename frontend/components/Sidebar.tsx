'use client'

import type { Conversation } from '@/types'

interface Props {
  conversations: Conversation[]
  activeId: string
  userEmail: string
  onSelect: (id: string) => void
  onNewChat: () => void
  onSignOut: () => void
  disabled?: boolean
}

export default function Sidebar({
  conversations,
  activeId,
  userEmail,
  onSelect,
  onNewChat,
  onSignOut,
  disabled = false,
}: Props) {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-gray-900">
      {/* Branding */}
      <div className="flex items-center gap-2.5 border-b border-white/10 px-4 py-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#FFD100] text-sm font-bold text-gray-900 shadow">
          CC
        </div>
        <div>
          <p className="text-sm font-semibold leading-none text-white">CourseCompass</p>
          <p className="mt-0.5 text-[10px] text-gray-400">UNSW Course Advisor</p>
        </div>
      </div>

      {/* New Chat */}
      <div className="px-3 pt-3 pb-2">
        <button
          onClick={onNewChat}
          disabled={disabled}
          className="flex w-full items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </div>

      {/* History label */}
      {conversations.length > 0 && (
        <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
          History
        </p>
      )}

      {/* Conversation list */}
      <nav className="flex-1 overflow-y-auto px-2">
        <ul className="space-y-0.5 pb-2">
          {conversations.map((conv) => (
            <li key={conv.id}>
              <button
                onClick={() => !disabled && onSelect(conv.id)}
                title={conv.title}
                className={`group flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  conv.id === activeId
                    ? 'bg-white/15 text-white'
                    : 'text-gray-400 hover:bg-white/10 hover:text-gray-200'
                } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
              >
                <svg
                  className="mr-2 h-3.5 w-3.5 shrink-0 opacity-60"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span className="truncate">{conv.title}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* User profile + sign out */}
      <div className="border-t border-white/10 px-3 py-3">
        <div className="flex items-center gap-2 rounded-lg px-2 py-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-500 text-xs font-semibold text-white">
            {userEmail ? userEmail[0].toUpperCase() : '?'}
          </div>
          <p className="flex-1 truncate text-xs text-gray-400">{userEmail}</p>
          <button
            onClick={onSignOut}
            title="Sign out"
            className="rounded p-1 text-gray-500 hover:bg-white/10 hover:text-gray-300 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  )
}
