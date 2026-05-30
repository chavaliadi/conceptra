import { useEffect, useState } from 'react'
import type { Concept, ConceptContent, ConceptStatus } from '../types'
import { getConceptContent } from '../api/client'

interface ConceptPanelProps {
  planId: string
  concept: Concept
  status: ConceptStatus
  onStatusChange: (status: ConceptStatus) => void
  onClose: () => void
}

const statusStyles: Record<ConceptStatus, string> = {
  untouched: 'bg-slate-700 text-slate-200',
  learned: 'bg-emerald-600 text-white',
  struggling: 'bg-amber-600 text-white',
  skipped: 'bg-rose-700 text-white',
}

const resourceIcons: Record<string, string> = {
  video: '🎬',
  docs: '📄',
  article: '📰',
}

export default function ConceptPanel({
  planId,
  concept,
  status,
  onStatusChange,
  onClose,
}: ConceptPanelProps) {
  const [content, setContent] = useState<ConceptContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revealedAnswers, setRevealedAnswers] = useState<Record<number, boolean>>({})
  const [selectedOptions, setSelectedOptions] = useState<Record<number, string>>({})

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setContent(null)
    setRevealedAnswers({})
    setSelectedOptions({})

    getConceptContent(planId, concept.id)
      .then((data) => {
        if (!cancelled) setContent(data)
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
  }, [planId, concept.id])

  return (
    <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-800 bg-slate-900 shadow-2xl">
      <div className="flex items-start justify-between border-b border-slate-800 p-5">
        <div>
          <span className={`rounded-full px-2 py-0.5 text-xs ${statusStyles[status]}`}>
            {status}
          </span>
          <h2 className="mt-2 text-xl font-semibold text-white">{concept.name}</h2>
          <p className="mt-1 text-sm text-slate-400">{concept.description}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {loading && <p className="text-slate-400">Loading content...</p>}
        {error && <p className="text-rose-400">{error}</p>}

        {content && (
          <div className="space-y-6">
            <section>
              <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-slate-400">
                Explanation
              </h3>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                {content.explanation.replace(/\*\*(.*?)\*\*/g, '$1')}
              </p>
            </section>

            <section>
              <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-400">
                Quiz
              </h3>
              <div className="space-y-4">
                {content.quiz.map((q, index) => (
                  <div key={index} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                    <p className="text-sm text-slate-200">{q.question}</p>
                    {q.type === 'mcq' && q.options && (
                      <div className="mt-3 space-y-2">
                        {q.options.map((option) => (
                          <button
                            key={option}
                            type="button"
                            onClick={() =>
                              setSelectedOptions((prev) => ({ ...prev, [index]: option }))
                            }
                            className={`block w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                              selectedOptions[index] === option
                                ? option === q.answer
                                  ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300'
                                  : 'border-rose-500 bg-rose-500/10 text-rose-300'
                                : 'border-slate-700 text-slate-300 hover:border-slate-600'
                            }`}
                          >
                            {option}
                          </button>
                        ))}
                      </div>
                    )}
                    {q.type === 'short_answer' && (
                      <button
                        type="button"
                        onClick={() =>
                          setRevealedAnswers((prev) => ({ ...prev, [index]: !prev[index] }))
                        }
                        className="mt-3 text-sm text-violet-400 hover:text-violet-300"
                      >
                        {revealedAnswers[index] ? 'Hide answer' : 'Reveal answer'}
                      </button>
                    )}
                    {q.type === 'short_answer' && revealedAnswers[index] && (
                      <p className="mt-2 rounded-lg bg-slate-800 p-3 text-sm text-slate-200">
                        {q.answer}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-400">
                Resources
              </h3>
              <div className="space-y-2">
                {content.resources.map((resource) => (
                  <a
                    key={resource.url}
                    href={resource.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-200 hover:border-violet-500/50 hover:bg-slate-900"
                  >
                    <span>{resourceIcons[resource.type] ?? '🔗'}</span>
                    <span>{resource.title}</span>
                  </a>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>

      <div className="border-t border-slate-800 p-5">
        <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Mark progress</p>
        <div className="grid grid-cols-3 gap-2">
          {(['learned', 'struggling', 'skipped'] as ConceptStatus[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onStatusChange(value)}
              className={`rounded-lg px-3 py-2 text-sm capitalize transition ${
                status === value
                  ? statusStyles[value]
                  : 'border border-slate-700 text-slate-300 hover:border-slate-600'
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}
