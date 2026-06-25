import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { getBenchmarkAnalytics } from '../api/client'

interface BenchmarkData {
  total_requests: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
  average_latency_ms: number
  cache_hit_rate_percent: number
  stage_timings: Record<string, { avg_latency_ms: number; count: number }>
}

export default function BenchmarkDashboard() {
  const { getToken, isSignedIn, isLoaded } = useAuth()
  const [data, setData] = useState<BenchmarkData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchBenchmarks = async () => {
    try {
      setLoading(true)
      const token = isSignedIn ? await getToken() : null
      const res = await getBenchmarkAnalytics(token)
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load operational benchmarks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!isLoaded) return
    fetchBenchmarks()
  }, [isLoaded, isSignedIn])

  return (
    <div className="relative min-h-[80vh]">
      {/* Decorative glows */}
      <div className="absolute -top-24 -left-24 w-80 h-80 bg-violet-600/10 rounded-full blur-[100px]" />
      <div className="absolute -bottom-24 -right-24 w-80 h-80 bg-emerald-600/5 rounded-full blur-[100px]" />

      <div className="relative z-10 space-y-10">
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <span className="inline-block text-[10px] font-extrabold tracking-wider text-violet-400 bg-violet-500/10 px-3 py-1 rounded-full uppercase">
            Operational Telemetry
          </span>
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            Pipeline Analytics &amp; Benchmarks
          </h1>
          <p className="text-slate-400 text-sm">
            Live telemetry displaying execution latency, token throughput, accumulated API costs, cache hits, and stage-by-stage timings for the LLM graph pipelines.
          </p>
        </div>

        {error && (
          <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-300 text-sm">
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-12 h-12 border-4 border-violet-500/20 border-t-violet-500 rounded-full animate-spin mb-4" />
            <p className="text-slate-400 text-sm">Loading telemetry metrics...</p>
          </div>
        ) : data ? (
          <div className="space-y-8 animate-fadeIn">
            {/* Summary KPI Cards */}
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
              {/* Request count */}
              <div className="p-5 rounded-2xl border border-slate-900 bg-slate-900/30 backdrop-blur-sm space-y-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Total LLM Calls</span>
                <p className="text-3xl font-extrabold text-white">{data.total_requests}</p>
                <p className="text-[10px] text-slate-400">Total pipeline invokes</p>
              </div>

              {/* Tokens */}
              <div className="p-5 rounded-2xl border border-slate-900 bg-slate-900/30 backdrop-blur-sm space-y-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Tokens Consumed</span>
                <p className="text-2xl font-extrabold text-white">
                  {((data.total_prompt_tokens + data.total_completion_tokens) / 1000).toFixed(1)}k
                </p>
                <p className="text-[10px] text-slate-400">
                  P: {(data.total_prompt_tokens / 1000).toFixed(1)}k | C: {(data.total_completion_tokens / 1000).toFixed(1)}k
                </p>
              </div>

              {/* Total cost */}
              <div className="p-5 rounded-2xl border border-slate-900 bg-slate-900/30 backdrop-blur-sm space-y-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Estimated Cost</span>
                <p className="text-3xl font-extrabold text-emerald-400">${data.total_cost_usd.toFixed(4)}</p>
                <p className="text-[10px] text-slate-400">Based on standard Groq rates</p>
              </div>

              {/* Latency */}
              <div className="p-5 rounded-2xl border border-slate-900 bg-slate-900/30 backdrop-blur-sm space-y-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Average Latency</span>
                <p className="text-3xl font-extrabold text-indigo-400">{(data.average_latency_ms / 1000).toFixed(2)}s</p>
                <p className="text-[10px] text-slate-400">Avg execution turnaround</p>
              </div>

              {/* Cache Hit */}
              <div className="p-5 rounded-2xl border border-slate-900 bg-slate-900/30 backdrop-blur-sm space-y-2">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Cache Hit Rate</span>
                <p className="text-3xl font-extrabold text-fuchsia-400">{data.cache_hit_rate_percent.toFixed(1)}%</p>
                <p className="text-[10px] text-slate-400">Redis cache bypass rate</p>
              </div>
            </div>

            {/* Stage timing breakdown list */}
            <div className="p-6 sm:p-8 rounded-3xl border border-slate-900 bg-slate-900/20 space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white">Pipeline Execution Stage Timings</h3>
                <p className="text-xs text-slate-400">Detailed latency breakdown per stage in the graph curriculum compilation sequence.</p>
              </div>

              <div className="space-y-4">
                {[
                  { key: 'concept_extraction', label: 'Stage 1: Concept Extraction', desc: 'LLM extracts core concepts based on text topic/syllabus parser.' },
                  { key: 'edge_generation', label: 'Stage 2: DAG Dependency Assembly', desc: 'LLM builds causal relationships between nodes (networkx validation).' },
                  { key: 'content_generation', label: 'Stage 3: Curriculum Content Synthesis', desc: 'LLM batch synthesizes explanations, quizzes, and resources.' },
                  { key: 'soft_grading', label: 'AI Helper: Soft Quiz Grading', desc: 'LLM performs open-ended grading comparing student replies to correct keys.' },
                  { key: 'edge_explanation', label: 'AI Helper: Prerequisite Edge Explainer', desc: 'LLM explains dependency reason between prerequisite nodes.' },
                  { key: 'chat', label: 'AI Helper: Chat Conversation', desc: 'LLM primes conversational follow-ups with student mastery memory profile.' }
                ].map((stage) => {
                  const stats = data.stage_timings[stage.key] || { avg_latency_ms: 0, count: 0 }
                  const isPresent = stats.count > 0
                  
                  return (
                    <div key={stage.key} className="p-4 rounded-xl border border-slate-900 bg-slate-950/40 grid grid-cols-1 md:grid-cols-12 items-center gap-4">
                      <div className="md:col-span-6 space-y-1">
                        <p className="text-xs font-bold text-slate-200">{stage.label}</p>
                        <p className="text-[10px] text-slate-400">{stage.desc}</p>
                      </div>
                      
                      <div className="md:col-span-3 text-left md:text-center text-xs">
                        <span className="text-slate-500 font-bold block text-[9px] uppercase">Executes Count</span>
                        <span className="text-slate-300 font-semibold">{stats.count} calls</span>
                      </div>

                      <div className="md:col-span-3 text-left md:text-right text-xs">
                        <span className="text-slate-500 font-bold block text-[9px] uppercase">Average Latency</span>
                        {isPresent ? (
                          <span className="text-sm font-extrabold text-violet-400">{(stats.avg_latency_ms / 1000).toFixed(2)} seconds</span>
                        ) : (
                          <span className="text-slate-500 font-mono text-xs">No metrics yet</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400 text-center py-12">No operational telemetry records available.</p>
        )}
      </div>
    </div>
  )
}
