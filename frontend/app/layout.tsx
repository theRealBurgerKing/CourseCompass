import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CourseCompass — UNSW Course Advisor',
  description: 'AI-powered course selection assistant for UNSW students',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}
