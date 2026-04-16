'use client'

import { useState } from 'react'
import type { Conversation } from '@/types'

interface Props {
  conversations: Conversation[]
  activeId: string
  userEmail: string
  avatarUrl: string
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  onSignOut: () => void
  onOpenSettings: () => void
  disabled?: boolean
}

export default function Sidebar({
  conversations,
  activeId,
  userEmail,
  avatarUrl,
  onSelect,
  onNewChat,
  onDelete,
  onSignOut,
  onOpenSettings,
  disabled = false,
}: Props) {
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const handleDeleteClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    setConfirmId(id)
  }

  const handleConfirm = () => {
    if (confirmId) onDelete(confirmId)
    setConfirmId(null)
  }

  const confirmTarget = conversations.find((c) => c.id === confirmId)

  return (
    <>
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
              <li key={conv.id} className="group relative">
                <button
                  onClick={() => !disabled && onSelect(conv.id)}
                  title={conv.title}
                  className={`flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition-colors pr-8 ${
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

                {/* Trash icon — visible on group hover */}
                <button
                  onClick={(e) => handleDeleteClick(e, conv.id)}
                  disabled={disabled}
                  title="删除会话"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-gray-600 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-white/10 hover:text-red-400 disabled:pointer-events-none"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* User profile — click to open settings */}
        <div className="border-t border-white/10 px-3 py-3">
          <button
            onClick={onOpenSettings}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-white/10"
          >
            <div className="h-7 w-7 shrink-0 overflow-hidden rounded-full">
              {avatarUrl ? (
                <img src={avatarUrl} alt="avatar" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-indigo-500 text-xs font-semibold text-white">
                  {userEmail ? userEmail[0].toUpperCase() : '?'}
                </div>
              )}
            </div>
            <p className="flex-1 truncate text-left text-xs text-gray-400">{userEmail}</p>
          </button>
        </div>
      </aside>

      {/* Confirm delete modal */}
      {confirmId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setConfirmId(null)}
        >
          <div
            className="w-80 rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-semibold text-gray-900">删除会话</h3>
            <p className="mt-2 text-sm text-gray-500">
              确定要删除「<span className="font-medium text-gray-700">{confirmTarget?.title}</span>」吗？此操作无法撤销。
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setConfirmId(null)}
                className="rounded-lg border border-gray-200 px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleConfirm}
                className="rounded-lg bg-red-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-600 transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
