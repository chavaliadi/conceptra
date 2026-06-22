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

  return (
    <div className="grid gap-6 md:grid-cols-3">
      
      {/* CARD 1: Radial Progress Ring */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex items-center justify-between shadow-md">
        <div className="space-y-1">
          <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Total Progress</h4>
          <p className="text-2xl font-bold text-white">{data.learned_count} / {data.total_concepts}</p>
          <p className="text-xs text-slate-400">concepts fully learned</p>
        </div>
        <div className="relative w-20 h-20 shrink-0">
          <svg className="w-full h-full transform -rotate-90">
            {/* Background Circle */}
            <circle
              cx="40"
              cy="40"
              r={radius}
              className="stroke-slate-800 fill-transparent"
              strokeWidth="6"
            />
            {/* Foreground Circle */}
            <circle
              cx="40"
              cy="40"
              r={radius}
              className="stroke-violet-500 fill-transparent transition-all duration-500 ease-out"
              strokeWidth="6"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-bold text-slate-200">{Math.round(data.progress_percentage)}%</span>
          </div>
        </div>
      </div>

      {/* CARD 2: Study Pacing & Velocity */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between shadow-md">
        <div className="space-y-1">
          <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Study Velocity</h4>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-2xl font-bold text-violet-400">{data.daily_velocity_needed}</span>
            <span className="text-xs text-slate-400">concepts / day</span>
          </div>
          <p className="text-xs text-slate-400">required pacing to hit exam goal</p>
        </div>
        <div className="border-t border-slate-850/80 pt-3 mt-4 flex justify-between items-center text-xs">
          <span className="text-slate-500">Days Remaining:</span>
          <span className="text-slate-200 font-bold">{data.days_left} days</span>
        </div>
      </div>

      {/* CARD 3: Target Projections */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 flex flex-col justify-between shadow-md relative overflow-hidden">
        <div className="absolute -right-8 -bottom-8 w-24 h-24 bg-violet-600/5 rounded-full blur-xl" />
        <div className="space-y-1 relative z-10">
          <div className="flex justify-between items-start gap-2">
            <h4 className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Pacing Assessment</h4>
            <span className={`px-2 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-widest ${statusBadgeStyles[data.status_assessment]}`}>
              {data.status_assessment}
            </span>
          </div>
          <div className="mt-2 text-sm text-slate-300">
            Projected completion:
            <span className="block text-base font-bold text-white mt-0.5">
              {new Date(data.projected_completion_date + 'T00:00:00').toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
              })}
            </span>
          </div>
        </div>
        <p className="text-[10px] text-slate-500 italic mt-4 relative z-10">
          *calculated using your {data.daily_velocity_needed} daily concept requirement.
        </p>
      </div>

    </div>
  )
}
