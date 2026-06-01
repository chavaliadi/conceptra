import { useState } from 'react'
import type { Plan } from '../types'

interface PlanHeaderProps {
  plan: Plan
  learnedCount: number
}

function daysUntilExam(examDate: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const exam = new Date(examDate + 'T00:00:00')
  const diff = exam.getTime() - today.getTime()
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)))
}

export default function PlanHeader({ plan, learnedCount }: PlanHeaderProps) {
  const [copied, setCopied] = useState(false)
  const total = plan.graph.concepts.length
  const daysLeft = daysUntilExam(plan.exam_date)
  const progress = total === 0 ? 0 : Math.round((learnedCount / total) * 100)

  function handleCopy() {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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
          </div>
          <p className="mt-2 text-sm text-slate-400">
            Exam on {new Date(plan.exam_date + 'T00:00:00').toLocaleDateString()} ·{' '}
            {plan.hours_per_day}h/day
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

