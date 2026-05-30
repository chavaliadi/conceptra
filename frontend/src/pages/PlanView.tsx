import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPlan } from '../api/client'
import ConceptPanel from '../components/ConceptPanel'
import PlanHeader from '../components/PlanHeader'
import type { Concept, ConceptStatus, Plan } from '../types'

const statusBorder: Record<ConceptStatus, string> = {
  untouched: 'border-slate-700 hover:border-slate-600',
  learned: 'border-emerald-500/60 bg-emerald-500/5',
  struggling: 'border-amber-500/60 bg-amber-500/5',
  skipped: 'border-rose-500/40 bg-rose-500/5 opacity-70',
}

function getPrerequisites(plan: Plan, conceptId: string): string[] {
  return plan.graph.edges
    .filter((edge) => edge.to_id === conceptId)
    .map((edge) => edge.from_id)
}

function isUnlocked(plan: Plan, conceptId: string, statuses: Record<string, ConceptStatus>): boolean {
  const prereqs = getPrerequisites(plan, conceptId)
  return prereqs.every((id) => statuses[id] === 'learned' || statuses[id] === 'skipped')
}

function loadStatuses(planId: string): Record<string, ConceptStatus> {
  try {
    const raw = localStorage.getItem(`conceptra-progress-${planId}`)
    return raw ? (JSON.parse(raw) as Record<string, ConceptStatus>) : {}
  } catch {
    return {}
  }
}

function saveStatuses(planId: string, statuses: Record<string, ConceptStatus>) {
  localStorage.setItem(`conceptra-progress-${planId}`, JSON.stringify(statuses))
}

export default function PlanView() {
  const { id } = useParams<{ id: string }>()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null)
  const [statuses, setStatuses] = useState<Record<string, ConceptStatus>>({})

  useEffect(() => {
    if (!id) return

    let cancelled = false
    setLoading(true)
    setError(null)

    getPlan(id)
      .then((data) => {
        if (cancelled) return
        setPlan(data)
        setStatuses(loadStatuses(id))
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [id])

  const learnedCount = useMemo(
    () => Object.values(statuses).filter((s) => s === 'learned').length,
    [statuses],
  )

  function getStatus(conceptId: string): ConceptStatus {
    return statuses[conceptId] ?? 'untouched'
  }

  function updateStatus(conceptId: string, status: ConceptStatus) {
    if (!id) return
    setStatuses((prev) => {
      const next = { ...prev, [conceptId]: status }
      saveStatuses(id, next)
      return next
    })
  }

  if (loading) {
    return <p className="text-center text-slate-400">Loading plan...</p>
  }

  if (error || !plan) {
    return (
      <p className="text-center text-rose-400">
        {error ?? 'Plan not found. It may have expired after a server restart.'}
      </p>
    )
  }

  return (
    <div>
      <PlanHeader plan={plan} learnedCount={learnedCount} />

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-medium text-white">Concept map</h2>
        <p className="text-sm text-slate-400">Click a concept to study · React Flow coming in Phase 2</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {plan.graph.concepts.map((concept) => {
          const status = getStatus(concept.id)
          const unlocked = isUnlocked(plan, concept.id, statuses)
          const schedule = plan.schedule.find((item) => item.concept_id === concept.id)

          return (
            <button
              key={concept.id}
              type="button"
              disabled={!unlocked}
              onClick={() => setSelectedConcept(concept)}
              className={`rounded-2xl border p-5 text-left transition ${statusBorder[status]} ${
                unlocked ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
              }`}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs uppercase tracking-wide text-slate-500">{status}</span>
                {schedule && (
                  <span className="text-xs text-slate-500">
                    W{schedule.week} D{schedule.day}
                  </span>
                )}
              </div>
              <h3 className="font-medium text-white">{concept.name}</h3>
              <p className="mt-2 line-clamp-2 text-sm text-slate-400">{concept.description}</p>
              {!unlocked && (
                <p className="mt-3 text-xs text-slate-500">Complete prerequisites first</p>
              )}
            </button>
          )
        })}
      </div>

      {selectedConcept && id && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50"
            onClick={() => setSelectedConcept(null)}
            aria-hidden="true"
          />
          <ConceptPanel
            planId={id}
            concept={selectedConcept}
            status={getStatus(selectedConcept.id)}
            onStatusChange={(status) => updateStatus(selectedConcept.id, status)}
            onClose={() => setSelectedConcept(null)}
          />
        </>
      )}
    </div>
  )
}
