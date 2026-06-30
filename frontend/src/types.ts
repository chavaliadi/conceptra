export interface Concept {
  id: string
  name: string
  description: string
}

export interface Edge {
  from_id: string
  to_id: string
}

export interface Graph {
  concepts: Concept[]
  edges: Edge[]
}

export interface ScheduleItem {
  concept_id: string
  week: number
  day: number
  priority: 'high' | 'medium' | 'low'
}

export interface QuizQuestion {
  type: 'mcq'
  question: string
  options: string[]
  correct_option_index: number
}

export interface Resource {
  type: 'video' | 'docs' | 'article'
  title: string
  url: string
  platform?: string
  query?: string
}

export interface ConceptContent {
  concept_id: string
  explanation: string
  quiz: QuizQuestion[]
  resources: Resource[]
}

export interface Plan {
  id: string
  topic: string
  exam_date: string | null
  hours_per_day: number
  graph: Graph
  schedule: ScheduleItem[]
  content: Record<string, ConceptContent>
  created_at: string
  is_public?: boolean
  clerk_user_id?: string | null
  forked_from_id?: string | null
  status?: 'completed' | 'generating' | 'failed'
}

export interface LibraryPlanItem {
  id: string
  topic: string
  hours_per_day: number
  exam_date?: string | null
  created_at: string
  concept_count: number
  clerk_user_id?: string | null
  forked_from_id?: string | null
}

export interface ForkResponse {
  original_plan_id: string
  new_plan_id: string
  topic: string
}

export interface CreatePlanRequest {
  topic: string
  exam_date: string
  hours_per_day: number
}

export interface CreatePlanResponse {
  id: string
}

export type ConceptStatus = 'untouched' | 'learned' | 'struggling' | 'skipped'

export interface DueReviewItem {
  id: string
  name: string
  description: string | null
  explanation: string
  quiz: QuizQuestion[]
  resources: Resource[]
  status: string
  next_review_at: string | null
}

export interface AnalyticsData {
  total_concepts: number
  learned_count: number
  struggling_count: number
  untouched_count: number
  skipped_count: number
  progress_percentage: number
  days_left: number
  daily_velocity_needed: number
  projected_completion_date: string
  status_assessment: 'On Track' | 'Behind' | 'Critical'
}

export interface TutorChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface QuizGradeRequest {
  question_id: string
  selected_option_index: number
  confidence_reported: number
  response_time_ms?: number
}

export interface QuizGradeResponse {
  correct: boolean
  score: number
  feedback: string
}

export interface LearningProfile {
  mastery_score: number
  confidence_score: number
  retention_score: number
  difficulty_score: number
  recommended_action: string | null
}


