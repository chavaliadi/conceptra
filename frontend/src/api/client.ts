import type {
  ConceptContent,
  CreatePlanRequest,
  CreatePlanResponse,
  Plan,
  ScheduleItem,
  DueReviewItem,
  AnalyticsData,
  LibraryPlanItem,
  ForkResponse,
  TutorChatMessage,
  QuizGradeRequest,
  QuizGradeResponse,
  LearningProfile,
} from '../types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers, ...restOptions } = options || {}
  const isMultipart = restOptions.body instanceof FormData
  const response = await fetch(path, {
    headers: {
      ...(isMultipart ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    ...restOptions,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }

  // Handle DELETE (204 No Content) responses which cannot be parsed as JSON
  if (response.status === 204) {
    return {} as T
  }

  return response.json() as Promise<T>
}

const isV2 = import.meta.env.VITE_API_VERSION === 'v2'
const API_PREFIX = isV2 ? '/api/v2/plans' : '/api/plans'

export function createPlan(body: CreatePlanRequest, token?: string | null): Promise<CreatePlanResponse> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<CreatePlanResponse>(API_PREFIX, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
}

export async function uploadSyllabus(
  file: File,
  examDate: string,
  hoursPerDay: number,
  token?: string | null,
): Promise<CreatePlanResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('exam_date', examDate)
  formData.append('hours_per_day', String(hoursPerDay))

  const url = isV2 ? '/api/v2/plans/upload-syllabus' : '/api/plans/upload-syllabus'
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Upload failed: ${response.status}`)
  }

  return response.json() as Promise<CreatePlanResponse>
}

export function getPlan(id: string, token?: string | null): Promise<Plan> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<Plan>(`${API_PREFIX}/${id}`, { headers })
}

export function getConceptContent(
  planId: string,
  conceptId: string,
  token?: string | null,
): Promise<ConceptContent> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<ConceptContent>(`${API_PREFIX}/${planId}/concepts/${conceptId}/content`, { headers })
}

export function getProgress(planId: string, token?: string | null): Promise<Record<string, string>> {
  if (!isV2) {
    return Promise.resolve({})
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<Record<string, string>>(`${API_PREFIX}/${planId}/progress`, { headers })
}

export function updateProgress(
  planId: string,
  conceptId: string,
  status: string,
  token?: string | null,
): Promise<{ status: string }> {
  if (!isV2) {
    return Promise.resolve({ status })
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<{ status: string }>(`${API_PREFIX}/${planId}/concepts/${conceptId}/progress`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ status }),
  })
}

export function listPlans(token?: string | null): Promise<Plan[]> {
  if (!isV2 || !token) {
    return Promise.resolve([])
  }
  return request<Plan[]>(API_PREFIX, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

export function deletePlan(id: string, token: string): Promise<void> {
  if (!isV2) {
    return Promise.resolve()
  }
  return request<void>(`${API_PREFIX}/${id}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

export function claimPlan(id: string, token: string): Promise<{ status: string; plan_id: string }> {
  if (!isV2) {
    return Promise.resolve({ status: 'ignored', plan_id: id })
  }
  return request<{ status: string; plan_id: string }>(`${API_PREFIX}/${id}/claim`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
}

export function replanSchedule(planId: string, token?: string | null): Promise<ScheduleItem[]> {
  if (!isV2) {
    // In V1 mode, return an empty array or handle mock locally
    return Promise.resolve([])
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<ScheduleItem[]>(`${API_PREFIX}/${planId}/replan`, {
    method: 'POST',
    headers,
  })
}

export function getDueReviews(planId: string, token?: string | null): Promise<DueReviewItem[]> {
  if (!isV2) {
    return Promise.resolve([])
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<DueReviewItem[]>(`${API_PREFIX}/${planId}/reviews/due`, { headers })
}

export function reviewConcept(
  planId: string,
  conceptId: string,
  rating: number,
  token?: string | null
): Promise<any> {
  if (!isV2) {
    return Promise.resolve({ status: 'learned' })
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<any>(`${API_PREFIX}/${planId}/concepts/${conceptId}/review`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ rating }),
  })
}

export function getAnalytics(planId: string, token?: string | null): Promise<AnalyticsData> {
  if (!isV2) {
    return Promise.resolve({
      total_concepts: 8,
      learned_count: 2,
      struggling_count: 1,
      untouched_count: 5,
      skipped_count: 0,
      progress_percentage: 25.0,
      days_left: 14,
      daily_velocity_needed: 0.43,
      projected_completion_date: new Date().toISOString().split('T')[0],
      status_assessment: 'On Track',
    })
  }
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<AnalyticsData>(`${API_PREFIX}/${planId}/analytics`, { headers })
}

export function publishPlan(
  planId: string,
  token?: string | null
): Promise<{ plan_id: string; is_public: boolean; action: string }> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<{ plan_id: string; is_public: boolean; action: string }>(
    `/api/v2/plans/${planId}/publish`,
    {
      method: 'POST',
      headers,
    }
  )
}

export function forkPlan(
  planId: string,
  token?: string | null
): Promise<ForkResponse> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<ForkResponse>(`/api/v2/plans/${planId}/fork`, {
    method: 'POST',
    headers,
  })
}

export function getLibrary(
  q?: string,
  sort: 'newest' | 'oldest' = 'newest',
  limit = 20,
  offset = 0,
  token?: string | null
): Promise<LibraryPlanItem[]> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const params = new URLSearchParams()
  if (q) params.append('q', q)
  params.append('sort', sort)
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return request<LibraryPlanItem[]>(`/api/v2/library?${params.toString()}`, {
    headers,
  })
}

export function getConceptProfile(
  planId: string,
  conceptId: string,
  token?: string | null
): Promise<LearningProfile> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<LearningProfile>(
    `/api/v2/plans/${planId}/concepts/${conceptId}/profile`,
    { headers }
  )
}

export function getChatHistory(
  planId: string,
  conceptId: string,
  token?: string | null
): Promise<TutorChatMessage[]> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<TutorChatMessage[]>(
    `/api/v2/plans/${planId}/concepts/${conceptId}/chat`,
    { headers }
  )
}

export function chatWithTutor(
  planId: string,
  conceptId: string,
  message: string,
  token?: string | null
): Promise<{ reply: string }> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<{ reply: string }>(
    `/api/v2/plans/${planId}/concepts/${conceptId}/chat`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ message }),
    }
  )
}

export function gradeQuizResponse(
  planId: string,
  conceptId: string,
  req: QuizGradeRequest,
  token?: string | null
): Promise<QuizGradeResponse> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<QuizGradeResponse>(
    `/api/v2/plans/${planId}/concepts/${conceptId}/quiz/grade`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(req),
    }
  )
}

export function getEdgeExplanation(
  fromConceptId: string,
  toConceptId: string,
  token?: string | null
): Promise<{ explanation: string }> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<{ explanation: string }>(
    `/api/v2/plans/edges/explanation?from_concept_id=${fromConceptId}&to_concept_id=${toConceptId}`,
    { headers }
  )
}

export function getWeeklyReport(
  planId: string,
  token?: string | null
): Promise<{
  concepts_mastered: number
  total_concepts: number
  average_confidence: number
  weaknesses: string[]
  recommendation: string
}> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<any>(`/api/v2/plans/${planId}/weekly-report`, { headers })
}

export function getBenchmarkAnalytics(
  token?: string | null
): Promise<{
  total_requests: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
  average_latency_ms: number
  cache_hit_rate_percent: number
  stage_timings: Record<string, { avg_latency_ms: number; count: number }>
}> {
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return request<any>(`/api/v2/plans/analytics/benchmarks`, { headers })
}
