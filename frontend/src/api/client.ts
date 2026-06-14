import type {
  ConceptContent,
  CreatePlanRequest,
  CreatePlanResponse,
  Plan,
} from '../types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function createPlan(body: CreatePlanRequest): Promise<CreatePlanResponse> {
  return request<CreatePlanResponse>('/api/plans', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function uploadSyllabus(
  file: File,
  examDate: string,
  hoursPerDay: number,
): Promise<CreatePlanResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('exam_date', examDate)
  formData.append('hours_per_day', String(hoursPerDay))

  const response = await fetch('/api/plans/upload-syllabus', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Upload failed: ${response.status}`)
  }

  return response.json() as Promise<CreatePlanResponse>
}

export function getPlan(id: string): Promise<Plan> {
  return request<Plan>(`/api/plans/${id}`)
}

export function getConceptContent(
  planId: string,
  conceptId: string,
): Promise<ConceptContent> {
  return request<ConceptContent>(`/api/plans/${planId}/concepts/${conceptId}/content`)
}
