import ReactMarkdown from 'react-markdown'
import type { Message } from '@/types'
import SourceCards from './SourceCards'

interface Props {
  message: Message
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-indigo-500 px-4 py-2.5 text-sm text-white shadow-sm">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3">
      {/* Avatar */}
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#FFD100] text-[11px] font-bold text-gray-900 shadow-sm">
        CC
      </div>

      <div className="max-w-[85%]">
        {/* Loading skeleton */}
        {message.content === '' ? (
          <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm border border-gray-100">
            <span className="h-2 w-2 rounded-full bg-gray-300 animate-bounce [animation-delay:-0.3s]" />
            <span className="h-2 w-2 rounded-full bg-gray-300 animate-bounce [animation-delay:-0.15s]" />
            <span className="h-2 w-2 rounded-full bg-gray-300 animate-bounce" />
          </div>
        ) : (
          <div className="rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm border border-gray-100">
            <div className="prose prose-sm prose-gray max-w-none text-gray-800 leading-relaxed">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
            {message.sources && <SourceCards sources={message.sources} />}
          </div>
        )}
      </div>
    </div>
  )
}
