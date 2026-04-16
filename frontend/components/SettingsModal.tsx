'use client'

import { useRef, useState } from 'react'
import { createClient } from '@/lib/supabase'

interface Props {
  userEmail: string
  avatarUrl: string
  userId: string
  conversations: { title: string; messages: { role: string; content: string }[] }[]
  onClose: () => void
  onSignOut: () => void
  onAvatarChange: (url: string) => void
}

export default function SettingsModal({
  userEmail,
  avatarUrl,
  userId,
  conversations,
  onClose,
  onSignOut,
  onAvatarChange,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [uploadError, setUploadError] = useState('')

  // ── Avatar upload ────────────────────────────────────────────────────────

  const handleAvatarClick = () => fileInputRef.current?.click()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadError('')
    setUploading(true)
    try {
      const supabase = createClient()
      const ext = file.name.split('.').pop()
      const path = `${userId}/avatar.${ext}`

      const { error: uploadErr } = await supabase.storage
        .from('avatars')
        .upload(path, file, { upsert: true })

      if (uploadErr) throw uploadErr

      const { data } = supabase.storage.from('avatars').getPublicUrl(path)
      const publicUrl = `${data.publicUrl}?t=${Date.now()}`

      await supabase.auth.updateUser({ data: { avatar_url: publicUrl } })
      onAvatarChange(publicUrl)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  // ── Export ───────────────────────────────────────────────────────────────

  const handleExport = async () => {
    setExporting(true)
    try {
      const supabase = createClient()

      const { data: convRows } = await supabase
        .from('conversations')
        .select('id, title, created_at')
        .order('updated_at', { ascending: false })

      if (!convRows) return

      const result = []
      for (const conv of convRows) {
        const { data: msgs } = await supabase
          .from('messages')
          .select('role, content, created_at')
          .eq('conversation_id', conv.id)
          .order('created_at', { ascending: true })

        result.push({ title: conv.title, created_at: conv.created_at, messages: msgs ?? [] })
      }

      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `coursecompass-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-96 rounded-2xl bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2">
          <h2 className="text-sm font-semibold text-gray-800">设置</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-5 space-y-6">

          {/* ── 账户 ── */}
          <section>
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-gray-400">账户</p>
            <div className="flex items-center gap-4">
              <button
                onClick={handleAvatarClick}
                disabled={uploading}
                className="group relative h-14 w-14 shrink-0 overflow-hidden rounded-full focus:outline-none"
                title="点击更换头像"
              >
                {avatarUrl ? (
                  <img src={avatarUrl} alt="avatar" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-indigo-500 text-lg font-semibold text-white">
                    {userEmail?.[0]?.toUpperCase() ?? '?'}
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
                  {uploading ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  )}
                </div>
              </button>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-800">{userEmail}</p>
                <p className="mt-0.5 text-xs text-gray-400">点击头像可更换图片</p>
                {uploadError && <p className="mt-1 text-xs text-red-500">{uploadError}</p>}
              </div>
            </div>
          </section>

          {/* ── Memory（占位符） ── */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-400">Memory</p>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-400">即将推出</span>
            </div>
            <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-5 text-center">
              <p className="text-sm text-gray-400">AI 将记住你的偏好和学习目标，提供更个性化的建议。</p>
            </div>
          </section>

          {/* ── 数据 ── */}
          <section>
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-gray-400">数据</p>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex w-full items-center gap-2 rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
            >
              {exporting ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
              ) : (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              )}
              {exporting ? '导出中…' : '导出全部对话记录（JSON）'}
            </button>
          </section>

          {/* ── 退出登录 ── */}
          <section>
            <button
              onClick={onSignOut}
              className="flex w-full items-center gap-2 rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-600 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              退出登录
            </button>
          </section>

        </div>
      </div>
    </div>
  )
}
