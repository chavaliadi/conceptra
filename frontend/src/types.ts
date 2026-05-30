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
  type: 'mcq' | 'short_answer'
  question: string
  options?: string[] | null
  answer: string
}

export interface Resource {
  type: 'video' | 'docs' | 'article'
  title: string
  url: string
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
  exam_date: string
  hours_per_day: number
  graph: Graph
  schedule: ScheduleItem[]
  content: Record<string, ConceptContent>
  created_at: string
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
