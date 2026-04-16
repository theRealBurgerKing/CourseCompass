export interface CourseSource {
  course_code: string
  course_name: string
  units_of_credit: string
  offering_terms: string
  faculty: string
  url?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: CourseSource[]
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
}
