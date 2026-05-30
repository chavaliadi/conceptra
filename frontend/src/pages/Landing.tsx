import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createPlan } from '../api/client'

function defaultExamDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 21)
  return date.toISOString().split('T')[0]
}

export default function Landing() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [examDate, setExamDate] = useState(defaultExamDate)
  const [hoursPerDay, setHoursPerDay] = useState(2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await createPlan({
        topic: topic.trim(),
        exam_date: examDate,
        hours_per_day: hoursPerDay,
      })
      navigate(`/plan/${response.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white">
          Turn any topic into a study plan
        </h1>
        <p className="mt-4 text-slate-400">
          Paste a subject or syllabus topic. Get a concept dependency map, schedule, and
          per-concept content — all in one shareable link.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900 p-8"
      >
        <div>
          <label htmlFor="topic" className="mb-2 block text-sm font-medium text-slate-300">
            Topic
          </label>
          <input
            id="topic"
            type="text"
            required
            placeholder='e.g. "Operating Systems" or "React Fundamentals"'
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          />
        </div>

        <div>
          <label htmlFor="exam-date" className="mb-2 block text-sm font-medium text-slate-300">
            Exam date
          </label>
          <input
            id="exam-date"
            type="date"
            required
            value={examDate}
            min={new Date().toISOString().split('T')[0]}
            onChange={(e) => setExamDate(e.target.value)}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          />
        </div>

        <div>
          <label htmlFor="hours" className="mb-2 block text-sm font-medium text-slate-300">
            Study hours per day: {hoursPerDay}h
          </label>
          <input
            id="hours"
            type="range"
            min={1}
            max={8}
            value={hoursPerDay}
            onChange={(e) => setHoursPerDay(Number(e.target.value))}
            className="w-full accent-violet-500"
          />
        </div>

        {error && (
          <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || !topic.trim()}
          className="w-full rounded-xl bg-violet-600 px-4 py-3 font-medium text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Creating your plan...' : 'Generate study plan'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Try &quot;Operating Systems&quot; or &quot;React Fundamentals&quot; for sample fixture data.
      </p>
    </div>
  )
}
