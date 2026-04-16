export interface CourseSource {
  course_code: string
  course_name: string
  units_of_credit: string
  offering_terms: string
  faculty: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: CourseSource[]
}

export interface ChatResponse {
  answer: string
  sources: CourseSource[]
  session_id: string
}
