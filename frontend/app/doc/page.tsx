export default function DocPage() {
  const resources = [
    {
      name: 'UNSW Handbook',
      url: 'https://www.handbook.unsw.edu.au/postgraduate/specialisations/2026/COMPMS',
      description: 'UNSW选课手册',
    },
    {
      name: 'Class Timetable',
      url: 'https://timetable.unsw.edu.au/2025/COMP9331.html',
      description: '查Class的时间地点',
    },
    {
      name: 'myPlan',
      url: 'https://myplan.unsw.edu.au/app/home',
      description: '检查是否满足毕业要求',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="mx-auto max-w-2xl">

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#FFD100] text-sm font-bold text-gray-900 shadow">
              CC
            </div>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">相关资料</h1>
              <p className="text-sm text-gray-400">CourseCompass 参考资源列表</p>
            </div>
          </div>
        </div>

        {/* Resource list */}
        <div className="space-y-3">
          {resources.map((r) => (
            <a
              key={r.url}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm transition-all hover:border-indigo-300 hover:shadow-md group"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-gray-800 group-hover:text-indigo-600 transition-colors">
                  {r.name}
                </p>
                <p className="mt-0.5 text-xs text-gray-400">{r.description}</p>
                <p className="mt-1 truncate text-[11px] text-gray-300">{r.url}</p>
              </div>
              <svg
                className="ml-4 h-4 w-4 shrink-0 text-gray-300 group-hover:text-indigo-400 transition-colors"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          ))}
        </div>

      </div>
    </div>
  )
}
