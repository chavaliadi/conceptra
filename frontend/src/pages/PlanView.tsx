import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPlan } from '../api/client'
import ConceptPanel from '../components/ConceptPanel'
import ConceptGraph from '../components/ConceptGraph'
import PlanHeader from '../components/PlanHeader'
import type { Concept, ConceptStatus, Plan } from '../types'

const statusBorder: Record<ConceptStatus, string> = {
  untouched: 'border-slate-800 hover:border-slate-700 bg-slate-900/40',
  learned: 'border-emerald-500/50 bg-emerald-500/5 shadow-sm shadow-emerald-950/20',
  struggling: 'border-amber-500/50 bg-amber-500/5 shadow-sm shadow-amber-950/20',
  skipped: 'border-rose-500/30 bg-rose-500/5 opacity-70',
}

const statusBadge: Record<ConceptStatus, string> = {
  untouched: 'bg-slate-950 text-slate-400 border border-slate-800',
  learned: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  struggling: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  skipped: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
}

const priorityLabel = {
  high: '🔥 High',
  medium: '⚡ Medium',
  low: '🌱 Low',
}

const priorityStyles = {
  high: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
  medium: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  low: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
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

  // Custom interactive layout modes
  const [viewMode, setViewMode] = useState<'map' | 'calendar'>('map')
  const [replanning, setReplanning] = useState(false)
  const [replanSuccess, setReplanSuccess] = useState(false)

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

  const strugglingCount = useMemo(
    () => Object.values(statuses).filter((s) => s === 'struggling').length,
    [statuses],
  )

  // Chronologically group the study calendar by weeks
  const weeksData = useMemo(() => {
    if (!plan) return []
    const groups: Record<number, { concept: Concept; day: number; priority: 'high' | 'medium' | 'low'; status: ConceptStatus }[]> = {}

    plan.schedule.forEach((item) => {
      const concept = plan.graph.concepts.find((c) => c.id === item.concept_id)
      if (!concept) return

      if (!groups[item.week]) {
        groups[item.week] = []
      }
      groups[item.week].push({
        concept,
        day: item.day,
        priority: item.priority,
        status: statuses[concept.id] ?? 'untouched',
      })
    })

    return Object.keys(groups)
      .map(Number)
      .sort((a, b) => a - b)
      .map((weekNum) => ({
        week: weekNum,
        items: groups[weekNum].sort((a, b) => a.day - b.day),
      }))
  }, [plan, statuses])

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

  function triggerReplan() {
    if (!plan) return
    setReplanning(true)

    setTimeout(() => {
      setReplanning(false)
      setReplanSuccess(true)

      // Perform mock AI schedule redistribution by changing priority and shifting order
      const updatedSchedule = plan.schedule.map((item) => {
        if (statuses[item.concept_id] === 'struggling') {
          // Escalating priority of struggling concepts
          return { ...item, priority: 'high' as const }
        }
        return item
      })

      setPlan({
        ...plan,
        schedule: updatedSchedule,
      })

      // Hide success notification after 3 seconds
      setTimeout(() => setReplanSuccess(false), 3000)
    }, 1800)
  }

  if (loading) {
    return <p className="text-center text-slate-400 my-12 animate-pulse">Loading plan...</p>
  }

  if (error || !plan) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-400 text-lg">
          {error ?? 'Plan not found. It may have expired after a server restart.'}
        </p>
        <a
          href="/"
          className="mt-4 inline-block text-sm text-violet-400 hover:text-violet-300 underline"
        >
          Return to home
        </a>
      </div>
    )
  }

  return (
    <div className="relative">
      <PlanHeader plan={plan} learnedCount={learnedCount} />

      {/* Adaptive Replanning Banner */}
      {strugglingCount >= 3 && (
        <div className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 shadow-lg relative overflow-hidden transition-all duration-300">
          <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-xl" />
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative z-10">
            <div>
              <h3 className="font-semibold text-amber-300 flex items-center gap-2">
                <span>⚠️</span> Adaptive Study Optimizer
              </h3>
              <p className="text-sm text-slate-300 mt-1">
                You have flagged <strong>{strugglingCount} concepts</strong> as struggling. Trigger a dynamic replanning session to prioritize these topics and adjust your calendar study density.
              </p>
            </div>
            <button
              onClick={triggerReplan}
              disabled={replanning}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs uppercase tracking-wider rounded-xl transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {replanning ? 'Redistributing...' : 'Replan Schedule'}
            </button>
          </div>
        </div>
      )}

      {/* Action Completed Notification banner */}
      {replanSuccess && (
        <div className="mb-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 shadow-lg text-emerald-400 font-medium text-sm flex items-center gap-2.5 animate-pulse">
          <span>✓</span> AI optimized study calendar! Struggling concepts escalated to priority high and redistributed.
        </div>
      )}

      {/* View Toggle Pill */}
      <div className="mb-6 flex justify-between items-center flex-wrap gap-4">
        <div className="flex gap-1 rounded-xl bg-slate-900 border border-slate-800 p-1">
          <button
            onClick={() => setViewMode('map')}
            className={`rounded-lg px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition duration-200 ${viewMode === 'map'
              ? 'bg-violet-600 text-white shadow'
              : 'text-slate-400 hover:text-slate-200'
              }`}
          >
            🗺️ Concept Map
          </button>
          <button
            onClick={() => setViewMode('calendar')}
            className={`rounded-lg px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition duration-200 ${viewMode === 'calendar'
              ? 'bg-violet-600 text-white shadow'
              : 'text-slate-400 hover:text-slate-200'
              }`}
          >
            📅 Study Calendar
          </button>
        </div>
        <p className="text-xs text-slate-500 italic">
          {viewMode === 'map' ? 'Click nodes to check concepts' : 'Follow week-by-week program'}
        </p>
      </div>

      {/* VIEW 1: Concept Map View */}
      {viewMode === 'map' && (
        <div>
          <div className="mb-4">
            <h2 className="text-lg font-medium text-white">Concept Map</h2>
            <p className="text-sm text-slate-400">Complete prerequisites to unlock advanced concepts.</p>
          </div>

          <div className="h-[600px]">
            <ConceptGraph
              plan={plan}
              statuses={statuses}
              onSelectConcept={setSelectedConcept}
            />
          </div>
        </div>
      )}

      {/* VIEW 2: Calendar View */}
      {viewMode === 'calendar' && (
        <div className="space-y-8">
          <div className="mb-4">
            <h2 className="text-lg font-medium text-white">Chronological Calendar</h2>
            <p className="text-sm text-slate-400">Sequential study plan matching topological sort dependencies.</p>
          </div>

          {weeksData.map(({ week, items }) => (
            <div key={week} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
              <h3 className="text-lg font-bold text-violet-400 mb-4 pb-2 border-b border-slate-800">
                Week {week}
              </h3>

              <div className="grid gap-4 md:grid-cols-2">
                {items.map(({ concept, day, priority, status }) => {
                  const unlocked = isUnlocked(plan, concept.id, statuses)

                  return (
                    <div
                      key={concept.id}
                      onClick={() => unlocked && setSelectedConcept(concept)}
                      className={`flex flex-col justify-between p-4 rounded-xl border transition duration-200 ${unlocked
                        ? 'cursor-pointer hover:border-violet-500/50 bg-slate-950/60'
                        : 'opacity-40 bg-slate-950/20 border-slate-800 cursor-not-allowed'
                        }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-500">Day {day}</span>
                          <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${statusBadge[status]}`}>
                            {status}
                          </span>
                        </div>
                        <h4 className="font-semibold text-white text-sm">{concept.name}</h4>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-1">{concept.description}</p>
                      </div>

                      <div className="flex justify-between items-center mt-4 pt-2 border-t border-slate-800/40">
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${priorityStyles[priority]}`}>
                          {priorityLabel[priority]}
                        </span>
                        <span className="text-xs text-slate-500">
                          {unlocked ? '🔓 Read' : '🔒 Locked'}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Concept drawer sidebar slide out */}
      {selectedConcept && id && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300"
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

