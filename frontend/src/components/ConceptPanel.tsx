import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/clerk-react'
import type { Concept, ConceptContent, ConceptStatus, TutorChatMessage, LearningProfile } from '../types'
import { getConceptContent, getConceptProfile, getChatHistory, gradeQuizResponse, chatWithTutor } from '../api/client'

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
  const { getToken } = useAuth()
  const [content, setContent] = useState<ConceptContent | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedOptions, setSelectedOptions] = useState<Record<number, string>>({})
  
  // Tab and Interactive States
  const [activeTab, setActiveTab] = useState<'study' | 'quiz' | 'tutor'>('study')
  const [shortAnswerInputs, setShortAnswerInputs] = useState<Record<number, string>>({})
  const [gradingResults, setGradingResults] = useState<Record<number, { correct: boolean; score: number; feedback: string }>>({})
  const [gradingLoading, setGradingLoading] = useState<Record<number, boolean>>({})

  // AI Tutor states
  const [messages, setMessages] = useState<TutorChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)
  const [profile, setProfile] = useState<LearningProfile | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setContent(null)
    setSelectedOptions({})
    setShortAnswerInputs({})
    setGradingResults({})
    setGradingLoading({})
    setMessages([])
    setProfile(null)

    const fetchContent = async () => {
      try {
        const token = await getToken()
        const data = await getConceptContent(planId, concept.id, token)
        if (!cancelled) setContent(data)
      } catch (err: any) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchContent()

    return () => {
      cancelled = true
    }
  }, [planId, concept.id])

  const fetchProfile = async () => {
    try {
      const token = await getToken()
      const data = await getConceptProfile(planId, concept.id, token)
      setProfile(data)
    } catch (err) {
      console.error('Failed to fetch profile', err)
    }
  }

  const fetchChat = async () => {
    try {
      const token = await getToken()
      const data = await getChatHistory(planId, concept.id, token)
      setMessages(data)
    } catch (err) {
      console.error('Failed to fetch chat history', err)
    }
  }

  const handleGradeQuiz = async (index: number, questionText: string, studentAnswer: string, correctAnswer: string) => {
    if (!studentAnswer.trim()) return
    try {
      setGradingLoading((prev) => ({ ...prev, [index]: true }))
      const token = await getToken()
      const res = await gradeQuizResponse(planId, concept.id, {
        question_id: String(index),
        question_text: questionText,
        student_answer: studentAnswer,
        correct_answer: correctAnswer,
      }, token)
      setGradingResults((prev) => ({ ...prev, [index]: res }))
      fetchProfile()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Quiz grading failed')
    } finally {
      setGradingLoading((prev) => ({ ...prev, [index]: false }))
    }
  }

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim() || sendingChat) return
    const userMsgText = chatInput
    setChatInput('')

    const tempUserMsg: TutorChatMessage = {
      id: Math.random().toString(),
      role: 'user',
      content: userMsgText,
      created_at: new Date().toISOString()
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      setSendingChat(true)
      const token = await getToken()
      const res = await chatWithTutor(planId, concept.id, userMsgText, token)
      const tempAsstMsg: TutorChatMessage = {
        id: Math.random().toString(),
        role: 'assistant',
        content: res.reply,
        created_at: new Date().toISOString()
      }
      setMessages((prev) => [...prev, tempAsstMsg])
      fetchProfile()
    } catch (err) {
      console.error(err)
    } finally {
      setSendingChat(false)
    }
  }

  return (
    <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-800 bg-slate-950 shadow-2xl">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-850 p-5 bg-slate-900/50">
        <div className="flex-1 min-w-0 pr-4">
          <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusStyles[status]}`}>
            {status}
          </span>
          <h2 className="mt-2 text-lg font-bold text-white truncate">{concept.name}</h2>
          <p className="mt-1 text-xs text-slate-400 line-clamp-2">{concept.description}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
          aria-label="Close panel"
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-900 bg-slate-950 px-2 select-none">
        <button
          onClick={() => setActiveTab('study')}
          className={`flex-1 py-3 text-[11px] font-bold uppercase tracking-wider text-center border-b-2 transition ${
            activeTab === 'study'
              ? 'border-violet-500 text-violet-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          📖 Study
        </button>
        <button
          onClick={() => setActiveTab('quiz')}
          className={`flex-1 py-3 text-[11px] font-bold uppercase tracking-wider text-center border-b-2 transition ${
            activeTab === 'quiz'
              ? 'border-violet-500 text-violet-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          📝 Quiz
        </button>
        <button
          onClick={() => {
            setActiveTab('tutor')
            fetchChat()
            fetchProfile()
          }}
          className={`flex-1 py-3 text-[11px] font-bold uppercase tracking-wider text-center border-b-2 transition ${
            activeTab === 'tutor'
              ? 'border-violet-500 text-violet-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          🤖 AI Tutor
        </button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-8 h-8 border-3 border-violet-500/20 border-t-violet-500 rounded-full animate-spin mb-3" />
            <p className="text-xs text-slate-500">Loading curriculum details...</p>
          </div>
        )}
        {error && <p className="text-xs text-rose-400 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl">⚠️ {error}</p>}

        {content && activeTab === 'study' && (
          <div className="space-y-6 animate-fadeIn">
            {/* Explanation Section */}
            <section className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Detailed Explanation
              </h3>
              <div className="rounded-xl border border-slate-900 bg-slate-900/30 p-4 leading-relaxed text-sm text-slate-200">
                {content.explanation.replace(/\*\*(.*?)\*\*/g, '$1')}
              </div>
            </section>

            {/* Resources Section */}
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Handpicked Resources
              </h3>
              <div className="grid gap-2">
                {content.resources.map((resource) => (
                  <a
                    key={resource.url}
                    href={resource.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-3 rounded-xl border border-slate-900 bg-slate-900/40 px-4 py-3 text-sm text-slate-300 hover:border-violet-500/40 hover:bg-slate-900 transition duration-200"
                  >
                    <span className="text-lg">{resourceIcons[resource.type] ?? '🔗'}</span>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-200 truncate">{resource.title}</p>
                      <p className="text-[10px] text-slate-500 truncate">{new URL(resource.url).hostname}</p>
                    </div>
                    <span className="text-slate-600 group-hover:text-slate-400 text-xs">&rarr;</span>
                  </a>
                ))}
              </div>
            </section>
          </div>
        )}

        {content && activeTab === 'quiz' && (
          <div className="space-y-5 animate-fadeIn">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Concept Checkpoints
            </h3>
            {content.quiz.map((q, index) => (
              <div key={index} className="rounded-xl border border-slate-900 bg-slate-900/30 p-4 space-y-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-md">
                  Q{index + 1}: {q.type === 'mcq' ? 'Multiple Choice' : 'Short Answer'}
                </span>
                <p className="text-sm font-semibold text-slate-200 leading-snug">{q.question}</p>
                
                {/* MCQ Question Mode */}
                {q.type === 'mcq' && q.options && (
                  <div className="grid gap-2 mt-2">
                    {q.options.map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() =>
                          setSelectedOptions((prev) => ({ ...prev, [index]: option }))
                        }
                        className={`block w-full rounded-xl border px-3.5 py-2.5 text-left text-xs transition duration-150 ${
                          selectedOptions[index] === option
                            ? option === q.answer
                              ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300 font-medium'
                              : 'border-rose-500 bg-rose-500/10 text-rose-300 font-medium'
                            : 'border-slate-800 text-slate-400 bg-slate-950/40 hover:border-slate-700 hover:text-slate-200'
                        }`}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}

                {/* Short Answer / Soft-Grading Mode */}
                {q.type === 'short_answer' && (
                  <div className="space-y-3">
                    <textarea
                      placeholder="Type your explanation answer here..."
                      value={shortAnswerInputs[index] ?? ''}
                      onChange={(e) =>
                        setShortAnswerInputs((prev) => ({ ...prev, [index]: e.target.value }))
                      }
                      rows={3}
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2.5 text-xs text-white placeholder-slate-650 focus:outline-none focus:border-violet-500 transition"
                    />
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] text-slate-500">Graded by Conceptra AI Tutor</span>
                      <button
                        type="button"
                        disabled={!shortAnswerInputs[index]?.trim() || gradingLoading[index]}
                        onClick={() =>
                          handleGradeQuiz(index, q.question, shortAnswerInputs[index], q.answer)
                        }
                        className="px-3.5 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-800 text-white disabled:text-slate-500 font-bold text-xs rounded-lg transition"
                      >
                        {gradingLoading[index] ? 'Grading...' : 'Submit Answer'}
                      </button>
                    </div>

                    {/* AI Grading Scorecard */}
                    {gradingResults[index] && (
                      <div className={`mt-3 p-3.5 rounded-xl border leading-relaxed text-xs space-y-2 ${
                        gradingResults[index].correct
                          ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300'
                          : 'border-rose-500/20 bg-rose-500/5 text-rose-300'
                      }`}>
                        <div className="flex justify-between items-center font-bold">
                          <span>{gradingResults[index].correct ? '✅ Concept Mastered' : '❌ Needs Improvement'}</span>
                          <span className="bg-white/10 px-2 py-0.5 rounded text-[10px]">
                            Score: {gradingResults[index].score}/100
                          </span>
                        </div>
                        <p className="text-slate-300 leading-snug">{gradingResults[index].feedback}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* AI Tutor conversational tab */}
        {activeTab === 'tutor' && (
          <div className="space-y-6 flex flex-col h-full animate-fadeIn">
            {/* Learning Profile Metrics Panel */}
            {profile && (
              <section className="p-4 rounded-xl border border-slate-900 bg-slate-900/20 space-y-3">
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Concept Mastery Profile
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <div className="flex justify-between text-slate-400 mb-1 text-[10px]">
                      <span>Mastery Score</span>
                      <span className="font-semibold text-slate-200">{profile.mastery_score.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                        style={{ width: `${profile.mastery_score}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-slate-400 mb-1 text-[10px]">
                      <span>Confidence</span>
                      <span className="font-semibold text-slate-200">{profile.confidence_score.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-violet-500 rounded-full transition-all duration-500"
                        style={{ width: `${profile.confidence_score}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-slate-400 mb-1 text-[10px]">
                      <span>Retention</span>
                      <span className="font-semibold text-slate-200">{profile.retention_score.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all duration-500"
                        style={{ width: `${profile.retention_score}%` }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-slate-400 mb-1 text-[10px]">
                      <span>Difficulty</span>
                      <span className="font-semibold text-slate-200">{profile.difficulty_score.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-rose-500 rounded-full transition-all duration-500"
                        style={{ width: `${profile.difficulty_score}%` }}
                      />
                    </div>
                  </div>
                </div>
                {profile.recommended_action && (
                  <p className="text-[10px] text-slate-400 bg-slate-950/50 p-2 rounded-lg border border-slate-900">
                    💡 <span className="font-medium text-slate-300">{profile.recommended_action}</span>
                  </p>
                )}
              </section>
            )}

            {/* Chat Box History */}
            <div className="flex-1 flex flex-col justify-end space-y-3">
              <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                {messages.length === 0 ? (
                  <div className="text-center py-10 text-slate-500 space-y-2">
                    <span className="text-2xl">💬</span>
                    <p className="text-xs">No conversation history yet. Ask any questions about {concept.name}!</p>
                  </div>
                ) : (
                  messages.map((msg, index) => (
                    <div
                      key={msg.id || index}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`rounded-xl px-3 py-2.5 text-xs max-w-[85%] leading-relaxed ${
                          msg.role === 'user'
                            ? 'bg-violet-600 text-white'
                            : 'bg-slate-900 border border-slate-850 text-slate-200'
                        }`}
                      >
                        {msg.content}
                      </div>
                    </div>
                  ))
                )}
                {sendingChat && (
                  <div className="flex justify-start">
                    <div className="rounded-xl px-3 py-2.5 text-xs max-w-[85%] bg-slate-900 border border-slate-850 text-slate-400 flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span>Tutor is thinking...</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Input box */}
              <form onSubmit={handleSendChat} className="flex gap-2 pt-2 border-t border-slate-900">
                <input
                  type="text"
                  placeholder="Ask a follow-up or ask to explain..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  className="flex-1 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-violet-500"
                />
                <button
                  type="submit"
                  disabled={!chatInput.trim() || sendingChat}
                  className="px-3 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-bold transition disabled:opacity-50"
                >
                  Send
                </button>
              </form>
            </div>
          </div>
        )}
      </div>

      {/* Footer / Mark Progress (Only for Study and Quiz tabs) */}
      {activeTab !== 'tutor' && (
        <div className="border-t border-slate-900 p-5 bg-slate-900/50">
          <p className="mb-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">Mark progress</p>
          <div className="grid grid-cols-3 gap-2">
            {(['learned', 'struggling', 'skipped'] as ConceptStatus[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => onStatusChange(value)}
                className={`rounded-lg px-3 py-2 text-xs font-bold capitalize transition ${
                  status === value
                    ? statusStyles[value]
                    : 'border border-slate-800 text-slate-400 bg-slate-950/40 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
