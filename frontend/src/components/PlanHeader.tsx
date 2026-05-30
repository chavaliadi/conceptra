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
  const total = plan.graph.concepts.length
  const daysLeft = daysUntilExam(plan.exam_date)
  const progress = total === 0 ? 0 : Math.round((learnedCount / total) * 100)

  return (
    <div className="mb-8 rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-400">Study plan</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">{plan.topic}</h1>
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
