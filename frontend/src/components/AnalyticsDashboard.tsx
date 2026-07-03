import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { getAnalytics } from '../api/client'
import type { AnalyticsData } from '../types'

interface AnalyticsDashboardProps {
  planId: string
  statuses: Record<string, string>
}

const statusBadgeStyles = {
  'On Track': 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  'Behind': 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  'Critical': 'bg-rose-500/10 text-rose-450 border border-rose-500/20',
}

export default function AnalyticsDashboard({ planId, statuses }: AnalyticsDashboardProps) {
  const { getToken, isLoaded } = useAuth()
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoaded) return

    const loadAnalytics = async () => {
      try {
        const token = await getToken()
        const analytics = await getAnalytics(planId, token)
        setData(analytics)
      } catch (err) {
        console.error('Failed to load analytics:', err)
      } finally {
        setLoading(false)
      }
    }

    loadAnalytics()
  }, [planId, statuses, isLoaded, getToken])

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/20 p-6 text-center animate-pulse">
        <p className="text-slate-400 text-xs uppercase tracking-wider">Recalculating study velocity...</p>
      </div>
    )
  }

  if (!data) return null

  // SVG parameters for radial progress circle
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (data.progress_percentage / 100) * circumference

  // SVG parameters for custom forgetting curve
  const curvePoints = data.retention_decay_curve || []
  const width = 600
  const height = 150
  const padding = 20
  const getX = (day: number) => padding + (day / 14) * (width - 2 * padding)
  const getY = (ret: number) => height - padding - (ret / 100) * (height - 2 * padding)

  let pathD = ""
  let areaD = ""

  if (curvePoints.length > 0) {
    pathD = `M ${getX(curvePoints[0].day)} ${getY(curvePoints[0].retention)}`
    areaD = `M ${getX(curvePoints[0].day)} ${getY(0)} L ${getX(curvePoints[0].day)} ${getY(curvePoints[0].retention)}`
    for (let i = 1; i < curvePoints.length; i++) {
      const p = curvePoints[i]
      pathD += ` L ${getX(p.day)} ${getY(p.retention)}`
      areaD += ` L ${getX(p.day)} ${getY(p.retention)}`
    }
    areaD += ` L ${getX(curvePoints[curvePoints.length - 1].day)} ${getY(0)} Z`
  }

  return (
    <div className="space-y-6">
      {/* ROW 1: 4 Analytics Cards */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        
        {/* CARD 1: Radial Progress Ring */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex items-center justify-between shadow-md">
          <div className="space-y-1">
            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Total Progress</h4>
            <p className="text-2xl font-bold text-white">{data.learned_count} / {data.total_concepts}</p>
            <p className="text-[10px] text-slate-400">concepts mastered</p>
          </div>
          <div className="relative w-16 h-16 shrink-0">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="32" cy="32" r="28" className="stroke-slate-800 fill-transparent" strokeWidth="5" />
              <circle
                cx="32"
                cy="32"
                r="28"
                className="stroke-emerald-500 fill-transparent transition-all duration-500 ease-out"
                strokeWidth="5"
                strokeDasharray={2 * Math.PI * 28}
                strokeDashoffset={2 * Math.PI * 28 - (data.progress_percentage / 100) * (2 * Math.PI * 28)}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[10px] font-bold text-slate-200">{Math.round(data.progress_percentage)}%</span>
            </div>
          </div>
        </div>

        {/* CARD 2: Study Pacing & Velocity */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between shadow-md">
          <div className="space-y-1">
            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Study Velocity</h4>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="text-2xl font-bold text-violet-400">{data.daily_velocity_needed}</span>
              <span className="text-xs text-slate-400">concepts / day</span>
            </div>
            <p className="text-[10px] text-slate-500">to complete by exam date</p>
          </div>
          <div className="border-t border-slate-850/80 pt-2 mt-3 flex justify-between items-center text-[10px]">
            <span className="text-slate-550">Days Remaining:</span>
            <span className="text-slate-200 font-semibold">{data.days_left} days</span>
          </div>
        </div>

        {/* CARD 3: Target Projections */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between shadow-md">
          <div className="space-y-1">
            <div className="flex justify-between items-start gap-2">
              <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Pacing Assessment</h4>
              <span className={`px-2 py-0.5 rounded-full text-[8px] uppercase font-bold tracking-widest ${statusBadgeStyles[data.status_assessment]}`}>
                {data.status_assessment}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-300">
              Projected completion:
              <span className="block text-sm font-semibold text-white mt-0.5">
                {new Date(data.projected_completion_date + 'T00:00:00').toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}
              </span>
            </div>
          </div>
          <p className="text-[9px] text-slate-500 italic mt-3">
            *based on active daily study hours budget.
          </p>
        </div>

        {/* CARD 4: Review Debt & Average Mastery */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between shadow-md">
          <div className="space-y-1">
            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">OS Registry Telemetry</h4>
            <div className="flex justify-between items-center mt-1">
              <div>
                <span className="text-xl font-bold text-rose-400">{data.review_debt}</span>
                <span className="text-[10px] text-slate-400 ml-1">debt items</span>
              </div>
              <span className="text-xs font-semibold text-indigo-400">{data.average_retention}% avg retention</span>
            </div>
            {data.review_debt > 0 ? (
              <span className="inline-block px-1.5 py-0.5 rounded text-[8px] bg-rose-500/10 text-rose-400 border border-rose-500/20 mt-1 font-semibold animate-pulse">
                ⚠️ Critical Memory Decay Detected
              </span>
            ) : (
              <span className="inline-block px-1.5 py-0.5 rounded text-[8px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mt-1 font-semibold">
                🛡️ Memory Cache Synced
              </span>
            )}
          </div>
          <div className="border-t border-slate-850/80 pt-2 mt-3 flex justify-between items-center text-[10px]">
            <span className="text-slate-550">Average Concept Mastery:</span>
            <span className="text-slate-200 font-semibold">{data.average_mastery}%</span>
          </div>
        </div>

      </div>

      {/* ROW 2: Ebbinghaus Forgetting Curve Chart */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/30 p-6 shadow-lg">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-slate-200">System Retention Decay Curve</h3>
          <p className="text-xs text-slate-450 mt-0.5">Projected retention index over the next 14 days if no review occurs (Ebbinghaus Forgetting Curve model).</p>
        </div>

        <div className="relative w-full overflow-hidden">
          {curvePoints.length > 0 ? (
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40 overflow-visible" preserveAspectRatio="none">
              <defs>
                <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.25"/>
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0"/>
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1={getX(0)} y1={getY(80)} x2={getX(14)} y2={getY(80)} stroke="#1e293b" strokeDasharray="3 3" />
              <text x={getX(14) - 90} y={getY(80) - 4} className="fill-slate-600 text-[8px] font-medium">80% Mastery Threshold</text>
              
              <line x1={getX(0)} y1={getY(50)} x2={getX(14)} y2={getY(50)} stroke="#1e293b" strokeDasharray="3 3" />
              <text x={getX(14) - 90} y={getY(50) - 4} className="fill-slate-650 text-[8px] font-medium">50% Decay Limit</text>

              {/* Shaded area under graph line */}
              {areaD && <path d={areaD} fill="url(#chartGradient)" />}

              {/* Graph line */}
              {pathD && <path d={pathD} fill="none" stroke="#8b5cf6" strokeWidth="2.5" strokeLinecap="round" />}

              {/* Labels & Markers at 2-day intervals */}
              {curvePoints.map((p, idx) => (
                (p.day % 2 === 0) && (
                  <g key={p.day}>
                    <circle cx={getX(p.day)} cy={getY(p.retention)} r="3" fill="#a78bfa" />
                    <text x={getX(p.day)} y={getY(p.retention) - 8} className="fill-violet-300 text-[8px] font-semibold text-center" textAnchor="middle">
                      {Math.round(p.retention)}%
                    </text>
                    <text x={getX(p.day)} y={height - 2} className="fill-slate-500 text-[8px] font-medium" textAnchor="middle">
                      {p.day === 0 ? "Today" : `Day ${p.day}`}
                    </text>
                  </g>
                )
              ))}
            </svg>
          ) : (
            <div className="h-40 flex items-center justify-center border border-dashed border-slate-800 rounded-xl">
              <p className="text-xs text-slate-500">Log quiz attempts to model your retention curve telemetry.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
