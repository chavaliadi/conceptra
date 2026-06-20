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

const isV2 = import.meta.env.VITE_API_VERSION === 'v2'
const API_PREFIX = isV2 ? '/api/v2/plans' : '/api/plans'

export function createPlan(body: CreatePlanRequest): Promise<CreatePlanResponse> {
  return request<CreatePlanResponse>(API_PREFIX, {
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

  // Keep upload syllabus hitting the main endpoint as it is fixture based for now
  const url = isV2 ? '/api/v2/plans/upload-syllabus' : '/api/plans/upload-syllabus'
  const response = await fetch(url, {
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
  return request<Plan>(`${API_PREFIX}/${id}`)
}

export function getConceptContent(
  planId: string,
  conceptId: string,
): Promise<ConceptContent> {
  return request<ConceptContent>(`${API_PREFIX}/${planId}/concepts/${conceptId}/content`)
}

export function getProgress(planId: string): Promise<Record<string, string>> {
  if (!isV2) {
    // Return empty for v1 fallback (it uses localStorage)
    return Promise.resolve({})
  }
  return request<Record<string, string>>(`${API_PREFIX}/${planId}/progress`)
}

export function updateProgress(
  planId: string,
  conceptId: string,
  status: string,
): Promise<{ status: string }> {
  if (!isV2) {
    return Promise.resolve({ status })
  }
  return request<{ status: string }>(`${API_PREFIX}/${planId}/concepts/${conceptId}/progress`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

