import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import { publishPlan } from '../api/client'
import type { Plan } from '../types'

interface PlanHeaderProps {
  plan: Plan
  learnedCount: number
}

function daysUntilExam(examDate: string | null | undefined): number {
  if (!examDate) return 0
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const exam = new Date(examDate + 'T00:00:00')
  const diff = exam.getTime() - today.getTime()
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
}

export default function PlanHeader({ plan, learnedCount }: PlanHeaderProps) {
  const { getToken, userId } = useAuth()
  const [copied, setCopied] = useState(false)
  const [isPublic, setIsPublic] = useState(plan.is_public ?? false)
  const [publishing, setPublishing] = useState(false)

  const isOwner = plan.clerk_user_id === userId
  const total = plan.graph.concepts.length
  const daysLeft = daysUntilExam(plan.exam_date)
  const progress = total === 0 ? 0 : Math.round((learnedCount / total) * 100)

  function handleCopy() {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function handlePublishToggle() {
    try {
      setPublishing(true)
      const token = await getToken()
      const res = await publishPlan(plan.id, token)
      setIsPublic(res.is_public)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to change visibility')
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-400">Study plan</p>
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            <h1 className="text-2xl font-semibold text-white">{plan.topic}</h1>
            <button
              type="button"
              onClick={handleCopy}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition duration-200 ${
                copied 
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' 
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800 text-slate-300 hover:text-white'
              }`}
            >
              <span className="text-xs">{copied ? '✓' : '🔗'}</span>
              <span>{copied ? 'Link copied!' : 'Share Plan'}</span>
            </button>
            {isOwner && (
              <button
                type="button"
                onClick={handlePublishToggle}
                disabled={publishing}
                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition duration-200 ${
                  isPublic
                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                    : 'border-violet-500/40 bg-violet-500/10 text-violet-400 hover:bg-violet-500/20'
                }`}
              >
                <span>{publishing ? '⏳' : isPublic ? '🌐' : '🔒'}</span>
                <span>{publishing ? 'Updating...' : isPublic ? 'Public' : 'Publish'}</span>
              </button>
            )}
            <Link
              to={`/plan/${plan.id}/review`}
              className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-violet-600 hover:bg-violet-500 px-2.5 py-1 text-xs text-white transition duration-200"
            >
              <span>🗂️</span>
              <span>Review Deck</span>
            </Link>
            {import.meta.env.VITE_API_VERSION === 'v2' && (
              <>
                <a
                  href={`/api/v2/plans/${plan.id}/export/pdf`}
                  download
                  className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800 px-2.5 py-1 text-xs text-slate-300 hover:text-white transition duration-200"
                >
                  <span>📄</span>
                  <span>Export PDF</span>
                </a>
                <a
                  href={`/api/v2/plans/${plan.id}/export/ics`}
                  download
                  className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800 px-2.5 py-1 text-xs text-slate-300 hover:text-white transition duration-200"
                >
                  <span>📅</span>
                  <span>Sync Calendar</span>
                </a>
              </>
            )}
          </div>
          <p className="mt-2 text-sm text-slate-400">
            {plan.exam_date
              ? <>Exam on {new Date(plan.exam_date + 'T00:00:00').toLocaleDateString()} · {plan.hours_per_day}h/day</>
              : <>{plan.hours_per_day}h/day</>}
          </p>
        </div>
        <div className="rounded-xl bg-slate-800 px-4 py-3 text-center">
          <p className="text-2xl font-bold text-violet-400">{daysLeft}</p>
          <p className="text-xs text-slate-400">days left</p>
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-2 flex justify-between text-sm text-slate-400">
          <span>
            {learnedCount} of {total} concepts learned
          </span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-violet-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  )
}

