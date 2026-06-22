import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import { getPlan, getProgress, updateProgress, claimPlan, replanSchedule } from '../api/client'
import ConceptPanel from '../components/ConceptPanel'
import ConceptGraph from '../components/ConceptGraph'
import PlanHeader from '../components/PlanHeader'
import AnalyticsDashboard from '../components/AnalyticsDashboard'
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
  const { getToken, isSignedIn } = useAuth()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null)
  const [statuses, setStatuses] = useState<Record<string, ConceptStatus>>({})

  // Custom interactive layout modes
  const [viewMode, setViewMode] = useState<'map' | 'calendar'>('map')
  const [replanning, setReplanning] = useState(false)
  const [replanSuccess, setReplanSuccess] = useState(false)

  // Local state for streaming logs
  const [streamStep, setStreamStep] = useState<string>('idle')
  const [streamLog, setStreamLog] = useState<string>('Initiating plan generation...')
  const [streamConcepts, setStreamConcepts] = useState<any[]>([])
  const [streamEdges, setStreamEdges] = useState<any[]>([])
  const [streamSchedule, setStreamSchedule] = useState<any[]>([])
  const [streamContent, setStreamContent] = useState<Record<string, any>>({})

  useEffect(() => {
    if (!id) return

    let cancelled = false
    let eventSource: EventSource | null = null

    const fetchPlan = async () => {
      try {
        const token = await getToken()
        const data = await getPlan(id, token)
        if (cancelled) return
        
        setPlan(data)
        setLoading(false)

        if (import.meta.env.VITE_API_VERSION === 'v2' && data.status === 'generating') {
          // Initialize EventSource
          const url = `/api/v2/plans/${id}/stream`
          eventSource = new EventSource(url)

          eventSource.addEventListener('generating_concepts', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('generating_concepts')
            setStreamLog(eventData.message)
          })

          eventSource.addEventListener('concepts_extracted', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('concepts_extracted')
            setStreamConcepts(eventData.concepts)
            setPlan((prev) => prev ? {
              ...prev,
              graph: { ...prev.graph, concepts: eventData.concepts }
            } : null)
          })

          eventSource.addEventListener('generating_graph', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('generating_graph')
            setStreamLog(eventData.message)
          })

          eventSource.addEventListener('graph_generated', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('graph_generated')
            setStreamEdges(eventData.edges)
            setPlan((prev) => prev ? {
              ...prev,
              graph: { ...prev.graph, edges: eventData.edges }
            } : null)
          })

          eventSource.addEventListener('generating_schedule', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('generating_schedule')
            setStreamLog(eventData.message)
          })

          eventSource.addEventListener('schedule_generated', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('schedule_generated')
            setStreamSchedule(eventData.schedule)
            setPlan((prev) => prev ? {
              ...prev,
              schedule: eventData.schedule
            } : null)
          })

          eventSource.addEventListener('generating_content', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('generating_content')
            setStreamLog(eventData.message)
          })

          eventSource.addEventListener('content_generated', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('content_generated')
            setStreamContent(eventData.content)
            setPlan((prev) => prev ? {
              ...prev,
              content: eventData.content
            } : null)
          })

          eventSource.addEventListener('completed', (event: any) => {
            const eventData = JSON.parse(event.data)
            setStreamStep('completed')
            setPlan((prev) => prev ? {
              ...prev,
              status: 'completed'
            } : null)
            eventSource?.close()
            // Fetch DB progress statuses
            getProgress(id, token).then((dbStatuses) => {
              if (!cancelled) {
                setStatuses({
                  ...loadStatuses(id),
                  ...(dbStatuses as Record<string, ConceptStatus>)
                })
              }
            }).catch(err => console.error('Failed to load progress from DB:', err))
          })

          eventSource.addEventListener('failed', (event: any) => {
            const eventData = JSON.parse(event.data)
            setError(eventData.error || 'Plan generation failed')
            setPlan((prev) => prev ? { ...prev, status: 'failed' } : null)
            eventSource?.close()
          })

          eventSource.onerror = (err) => {
            console.error('EventSource failed:', err)
          }
        } else if (import.meta.env.VITE_API_VERSION === 'v2') {
          try {
            const dbStatuses = await getProgress(id, token)
            if (cancelled) return
            setStatuses({
              ...loadStatuses(id),
              ...(dbStatuses as Record<string, ConceptStatus>)
            })
          } catch (err) {
            console.error('Failed to load progress from DB:', err)
            setStatuses(loadStatuses(id))
          }
        } else {
          setStatuses(loadStatuses(id))
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      }
    }

    setLoading(true)
    setError(null)
    fetchPlan()

    return () => {
      cancelled = true
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [id, getToken])

  useEffect(() => {
    if (isSignedIn && id && import.meta.env.VITE_API_VERSION === 'v2') {
      const claimAnonymousPlan = async () => {
        try {
          const token = await getToken()
          if (token) {
            await claimPlan(id, token)
          }
        } catch (err) {
          console.log('Claim plan failed/already claimed:', err)
        }
      }
      claimAnonymousPlan()
    }
  }, [isSignedIn, id, getToken])

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

  async function updateStatus(conceptId: string, status: ConceptStatus) {
    if (!id) return
    setStatuses((prev) => {
      const next = { ...prev, [conceptId]: status }
      saveStatuses(id, next)
      return next
    })
    
    if (import.meta.env.VITE_API_VERSION === 'v2') {
      try {
        const token = await getToken()
        await updateProgress(id, conceptId, status, token)
      } catch (err) {
        console.error('Failed to update progress in DB:', err)
      }
    }
  }

  async function triggerReplan() {
    if (!plan || !id) return
    setReplanning(true)

    if (import.meta.env.VITE_API_VERSION === 'v2') {
      try {
        const token = await getToken()
        const updatedSchedule = await replanSchedule(id, token)
        setPlan({
          ...plan,
          schedule: updatedSchedule,
        })
        setReplanSuccess(true)
      } catch (err) {
        console.error('Failed to replan schedule:', err)
        alert(err instanceof Error ? err.message : 'Replanning failed')
      } finally {
        setReplanning(false)
        setTimeout(() => setReplanSuccess(false), 3000)
      }
    } else {
      // V1 Mock Fallback
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

  if (plan.status === 'generating') {
    const isStepActive = (step: string) => streamStep === step
    const isStepDone = (stepList: string[], current: string) => {
      const idx = stepList.indexOf(current)
      const activeIdx = stepList.indexOf(streamStep)
      return activeIdx > idx || streamStep === 'completed'
    }
    const stepsOrder = [
      'generating_concepts',
      'concepts_extracted',
      'generating_graph',
      'graph_generated',
      'generating_schedule',
      'schedule_generated',
      'generating_content',
      'content_generated'
    ]

    return (
      <div className="flex flex-col items-center justify-center min-h-[450px] text-center p-8 bg-slate-900/40 border border-slate-800 rounded-3xl max-w-xl mx-auto my-12 shadow-2xl relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-violet-600/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" />
        
        <div className="relative z-10 space-y-6 w-full">
          <div className="relative w-20 h-20 mx-auto">
            <div className="absolute inset-0 border-4 border-violet-500/20 rounded-full" />
            <div className="absolute inset-0 border-4 border-transparent border-t-violet-500 border-r-fuchsia-500 rounded-full animate-spin" />
            <span className="absolute inset-0 flex items-center justify-center text-2xl">🧠</span>
          </div>
          
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-white tracking-tight">Generating Study Plan</h2>
            <p className="text-violet-400 text-sm font-medium animate-pulse">{streamLog}</p>
          </div>
          
          <div className="border border-slate-800/80 bg-slate-950/60 rounded-2xl p-5 flex flex-col items-start space-y-4 max-w-md mx-auto text-left w-full">
            {/* Step 1: Extract Concepts */}
            <div className="flex flex-col w-full">
              <div className="flex items-center gap-3 text-xs">
                {isStepActive('generating_concepts') ? (
                  <span className="w-2.5 h-2.5 rounded-full bg-violet-500 animate-ping shrink-0" />
                ) : isStepDone(stepsOrder, 'generating_concepts') ? (
                  <span className="text-emerald-400 font-bold text-sm shrink-0">✓</span>
                ) : (
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-800 shrink-0" />
                )}
                <span className={`font-medium ${isStepActive('generating_concepts') ? 'text-white' : 'text-slate-400'}`}>
                  Extracting core concepts...
                </span>
              </div>
              {streamConcepts.length > 0 && (
                <div className="mt-2 pl-6 flex flex-wrap gap-1.5 transition-all duration-300">
                  {streamConcepts.map((c, i) => (
                    <span key={i} className="text-[10px] bg-slate-900 border border-slate-800 text-slate-300 px-2 py-0.5 rounded-md">
                      {c.name}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Step 2: Relationships */}
            <div className="flex flex-col w-full">
              <div className="flex items-center gap-3 text-xs">
                {isStepActive('generating_graph') ? (
                  <span className="w-2.5 h-2.5 rounded-full bg-violet-500 animate-ping shrink-0" />
                ) : isStepDone(stepsOrder, 'generating_graph') ? (
                  <span className="text-emerald-400 font-bold text-sm shrink-0">✓</span>
                ) : (
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-800 shrink-0" />
                )}
                <span className={`font-medium ${isStepActive('generating_graph') ? 'text-white' : 'text-slate-400'}`}>
                  Formulating dependency graph (DAG)...
                </span>
              </div>
              {streamEdges.length > 0 && (
                <div className="mt-1.5 pl-6 text-[10px] text-violet-400 font-mono">
                  ⚡ Connected {streamEdges.length} concept dependencies
                </div>
              )}
            </div>

            {/* Step 3: Calendar & Study Guide */}
            <div className="flex flex-col w-full">
              <div className="flex items-center gap-3 text-xs">
                {(isStepActive('generating_schedule') || isStepActive('generating_content')) ? (
                  <span className="w-2.5 h-2.5 rounded-full bg-violet-500 animate-ping shrink-0" />
                ) : isStepDone(stepsOrder, 'generating_content') ? (
                  <span className="text-emerald-400 font-bold text-sm shrink-0">✓</span>
                ) : (
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-800 shrink-0" />
                )}
                <span className={`font-medium ${(isStepActive('generating_schedule') || isStepActive('generating_content')) ? 'text-white' : 'text-slate-400'}`}>
                  Synthesizing learning guides & quizzes...
                </span>
              </div>
              {Object.keys(streamContent).length > 0 && (
                <div className="mt-1.5 pl-6 text-[10px] text-emerald-400 font-mono">
                  📖 Explanations & flashcards completed
                </div>
              )}
            </div>
          </div>
          
          <p className="text-xs text-slate-500 italic animate-pulse">Running advanced learning analytics engine...</p>
        </div>
      </div>
    )
  }

  if (plan.status === 'failed') {
    return (
      <div className="text-center py-12 max-w-md mx-auto">
        <div className="text-rose-500 text-5xl mb-4">⚠️</div>
        <h2 className="text-lg font-bold text-white mb-2">Generation Failed</h2>
        <p className="text-slate-400 text-sm mb-6">
          The AI pipeline encountered an issue establishing the dependency graph or parsing the concept details for this topic.
        </p>
        <div className="flex justify-center gap-4">
          <a
            href="/"
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition duration-200"
          >
            Return to home
          </a>
        </div>
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

      {/* Progress Analytics Dashboard */}
      {import.meta.env.VITE_API_VERSION === 'v2' && (
        <div className="mb-8">
          <AnalyticsDashboard planId={id} statuses={statuses} />
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

