import { describe, it, expect } from 'vitest'
import type { ConceptStatus, ConceptProgressDetail, Edge } from '../../types'

// Replicating the core status resolution functions from ConceptGraph.tsx
export function computeIsBlocked(
  conceptId: string,
  edges: Edge[],
  statuses: Record<string, ConceptStatus>
): boolean {
  const prereqs = edges
    .filter((e) => e.to_id === conceptId)
    .map((e) => e.from_id)
  if (prereqs.length === 0) return false
  return prereqs.some((pid) => {
    const pStatus = statuses[pid] ?? 'untouched'
    return pStatus !== 'learned' && pStatus !== 'skipped'
  })
}

export function computeIsForgotten(
  conceptId: string,
  progressDetails?: Record<string, ConceptProgressDetail>
): boolean {
  const detail = progressDetails?.[conceptId]
  if (!detail) return false
  if (detail.status !== 'learned') return false
  const isRetentionDecayed = detail.retention_pct < 50
  const isOverdue = detail.next_review_at ? new Date(detail.next_review_at) <= new Date() : false
  return isRetentionDecayed || isOverdue
}

export function resolveNodeStatus(
  conceptId: string,
  edges: Edge[],
  statuses: Record<string, ConceptStatus>,
  progressDetails?: Record<string, ConceptProgressDetail>
): 'blocked' | 'ready' | 'learned' | 'struggling' | 'forgotten' | 'skipped' {
  const baseStatus = statuses[conceptId] ?? 'untouched'

  if (baseStatus === 'skipped') {
    return 'skipped'
  } else if (baseStatus === 'struggling') {
    return 'struggling'
  } else if (baseStatus === 'learned') {
    return computeIsForgotten(conceptId, progressDetails) ? 'forgotten' : 'learned'
  } else {
    return computeIsBlocked(conceptId, edges, statuses) ? 'blocked' : 'ready'
  }
}

describe('ConceptGraph Status Computation', () => {
  const sampleEdges: Edge[] = [
    { from_id: 'c1', to_id: 'c2' },
    { from_id: 'c2', to_id: 'c3' },
  ]

  describe('isBlocked', () => {
    it('returns false for root concepts with no prerequisites', () => {
      const statuses: Record<string, ConceptStatus> = { c1: 'untouched' }
      expect(computeIsBlocked('c1', sampleEdges, statuses)).toBe(false)
    })

    it('returns true if any prerequisite is untouched or struggling', () => {
      const statuses1: Record<string, ConceptStatus> = { c1: 'untouched', c2: 'untouched' }
      expect(computeIsBlocked('c2', sampleEdges, statuses1)).toBe(true)

      const statuses2: Record<string, ConceptStatus> = { c1: 'struggling', c2: 'untouched' }
      expect(computeIsBlocked('c2', sampleEdges, statuses2)).toBe(true)
    })

    it('returns false if all prerequisites are learned or skipped', () => {
      const statusesLearned: Record<string, ConceptStatus> = { c1: 'learned', c2: 'untouched' }
      expect(computeIsBlocked('c2', sampleEdges, statusesLearned)).toBe(false)

      const statusesSkipped: Record<string, ConceptStatus> = { c1: 'skipped', c2: 'untouched' }
      expect(computeIsBlocked('c2', sampleEdges, statusesSkipped)).toBe(false)
    })
  })

  describe('isForgotten', () => {
    it('returns false if concept is not learned', () => {
      const details: Record<string, ConceptProgressDetail> = {
        c1: { status: 'struggling', mastery_pct: 30, retention_pct: 20, next_review_at: null },
      }
      expect(computeIsForgotten('c1', details)).toBe(false)
    })

    it('returns true if retention falls below 50%', () => {
      const details: Record<string, ConceptProgressDetail> = {
        c1: {
          status: 'learned',
          mastery_pct: 85,
          retention_pct: 45,
          next_review_at: new Date(Date.now() + 86400000).toISOString(),
        },
      }
      expect(computeIsForgotten('c1', details)).toBe(true)
    })

    it('returns true if review date has passed', () => {
      const details: Record<string, ConceptProgressDetail> = {
        c1: {
          status: 'learned',
          mastery_pct: 90,
          retention_pct: 80,
          next_review_at: new Date(Date.now() - 86400000).toISOString(),
        },
      }
      expect(computeIsForgotten('c1', details)).toBe(true)
    })

    it('returns false if concept is healthy and not overdue', () => {
      const details: Record<string, ConceptProgressDetail> = {
        c1: {
          status: 'learned',
          mastery_pct: 95,
          retention_pct: 90,
          next_review_at: new Date(Date.now() + 86400000).toISOString(),
        },
      }
      expect(computeIsForgotten('c1', details)).toBe(false)
    })
  })

  describe('resolveNodeStatus', () => {
    it('resolves ready, blocked, learned, struggling, forgotten, skipped correctly', () => {
      const edges: Edge[] = [{ from_id: 'c1', to_id: 'c2' }]

      // c1 untouched root -> ready
      expect(resolveNodeStatus('c1', edges, { c1: 'untouched' })).toBe('ready')

      // c2 with c1 untouched -> blocked
      expect(resolveNodeStatus('c2', edges, { c1: 'untouched', c2: 'untouched' })).toBe('blocked')

      // c2 with c1 learned -> ready
      expect(resolveNodeStatus('c2', edges, { c1: 'learned', c2: 'untouched' })).toBe('ready')

      // c1 struggling -> struggling
      expect(resolveNodeStatus('c1', edges, { c1: 'struggling' })).toBe('struggling')

      // c1 skipped -> skipped
      expect(resolveNodeStatus('c1', edges, { c1: 'skipped' })).toBe('skipped')

      // c1 learned healthy -> learned
      const healthyDetails = {
        c1: { status: 'learned' as const, mastery_pct: 90, retention_pct: 85, next_review_at: new Date(Date.now() + 100000).toISOString() }
      }
      expect(resolveNodeStatus('c1', edges, { c1: 'learned' }, healthyDetails)).toBe('learned')

      // c1 learned but decayed -> forgotten
      const decayedDetails = {
        c1: { status: 'learned' as const, mastery_pct: 90, retention_pct: 40, next_review_at: new Date(Date.now() + 100000).toISOString() }
      }
      expect(resolveNodeStatus('c1', edges, { c1: 'learned' }, decayedDetails)).toBe('forgotten')
    })
  })
})
