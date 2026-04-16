'use client'

import { useRef, type KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  disabled: boolean
}

export default function ChatInput({ value, onChange, onSubmit, disabled }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!disabled && value.trim()) onSubmit()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-md focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100 transition-all">
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          handleInput()
        }}
        onKeyDown={handleKeyDown}
        placeholder="Ask about UNSW courses… (Enter to send, Shift+Enter for newline)"
        disabled={disabled}
        className="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none leading-relaxed disabled:opacity-50"
      />

      <button
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-xl bg-indigo-500 text-white shadow-sm transition-all hover:bg-indigo-600 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
        aria-label="Send message"
      >
        <svg className="h-4 w-4 translate-x-0.5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </button>
    </div>
  )
}
