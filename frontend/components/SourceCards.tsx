'use client'

import { useState } from 'react'
import type { CourseSource } from '@/types'

interface Props {
  sources: CourseSource[]
}

export default function SourceCards({ sources }: Props) {
  const [open, setOpen] = useState(false)

  if (sources.length === 0) return null

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-indigo-500 hover:text-indigo-700 font-medium transition-colors"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        {sources.length} referenced course{sources.length > 1 ? 's' : ''}
      </button>

      {open && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {sources.map((s) => (
            <a
              key={s.course_code}
              href={s.url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-gray-200 bg-white px-3 py-2.5 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all block"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-semibold text-indigo-600 text-sm">
                  {s.course_code}
                </span>
                <span className="shrink-0 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-500">
                  {s.units_of_credit.replace(' Units of Credit', 'UoC')}
                </span>
              </div>
              <p className="mt-0.5 text-[13px] text-gray-700 leading-snug">
                {s.course_name}
              </p>
              {s.offering_terms && (
                <p className="mt-1.5 text-[11px] text-gray-400">
                  {s.offering_terms}
                </p>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
