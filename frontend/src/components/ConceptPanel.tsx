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

function parseExplanationSections(text: string) {
  const sections: { title: string; content: string; icon: string; style: string }[] = [];
  const regex = /(💡\s*(?:\*\*)?Analogy(?:\*\*)?:|🌐\s*(?:\*\*)?Real-World Example(?:\*\*)?:|🎯\s*(?:\*\*)?Exam Tip(?:\*\*)?:|⚠️\s*(?:\*\*)?Frequently Confused With(?:\*\*)?:|📚\s*(?:\*\*)?Recommended Reading(?:\*\*)?:)/g;
  
  const parts = text.split(regex);
  if (parts.length === 1) {
    sections.push({
      title: 'Detailed Explanation',
      content: text,
      icon: '📖',
      style: 'border-slate-800 bg-slate-900/10 text-slate-200'
    });
    return sections;
  }
  
  if (parts[0].trim()) {
    sections.push({
      title: 'Concept Explanation',
      content: parts[0].trim(),
      icon: '📖',
      style: 'border-slate-900/60 bg-slate-900/20 text-slate-200'
    });
  }
  
  for (let i = 1; i < parts.length; i += 2) {
    const titleHeader = parts[i];
    const sectionBody = parts[i + 1] ? parts[i + 1].trim() : '';
    if (!sectionBody) continue;
    
    let title = 'Section';
    let icon = '💡';
    let style = 'border-slate-800 bg-slate-900/10 text-slate-200';
    
    if (titleHeader.includes('💡')) {
      title = 'Analogy';
      icon = '💡';
      style = 'border-amber-500/20 bg-amber-500/5 text-amber-200';
    } else if (titleHeader.includes('🌐')) {
      title = 'Real-World Example';
      icon = '🌐';
      style = 'border-sky-500/20 bg-sky-500/5 text-sky-200';
    } else if (titleHeader.includes('🎯')) {
      title = 'Exam Tip';
      icon = '🎯';
      style = 'border-emerald-500/20 bg-emerald-500/5 text-emerald-200 font-medium';
    } else if (titleHeader.includes('⚠️')) {
      title = 'Frequently Confused With';
      icon = '⚠️';
      style = 'border-rose-500/20 bg-rose-500/5 text-rose-200';
    } else if (titleHeader.includes('📚')) {
      title = 'Recommended Reading';
      icon = '📚';
      style = 'border-violet-500/20 bg-violet-500/5 text-violet-200';
    }
    
    sections.push({ title, content: sectionBody, icon, style });
  }
  return sections;
}

export default function ConceptPanel({
  planId,
  concept,
  status,
  onStatusChange,
  onClose,
}: ConceptPanelProps) {
  const { getToken } = useAuth()
  const [selectedOptions, setSelectedOptions] = useState<Record<number, number>>({})
  const [selectedConfidence, setSelectedConfidence] = useState<Record<number, number>>({})
  const [flaggedQuestions, setFlaggedQuestions] = useState<Record<number, boolean>>({})
  
  // Tab and Interactive States
  const [activeTab, setActiveTab] = useState<'study' | 'quiz' | 'tutor'>('study')
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
    setSelectedConfidence({})
    setFlaggedQuestions({})
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
 
  const handleGradeQuiz = async (index: number, selectedOptionIndex: number, confidenceReported: number) => {
    try {
      setGradingLoading((prev) => ({ ...prev, [index]: true }))
      const token = await getToken()
      const res = await gradeQuizResponse(planId, concept.id, {
        question_id: String(index),
        selected_option_index: selectedOptionIndex,
        confidence_reported: confidenceReported,
        response_time_ms: 0,
      }, token)
      setGradingResults((prev) => ({ ...prev, [index]: res }))
      fetchProfile()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Quiz grading failed')
    } finally {
      setGradingLoading((prev) => ({ ...prev, [index]: false }))
    }
  }

  const handleFlagQuestion = async (index: number, questionText: string) => {
    try {
      const token = await getToken()
      const url = `/api/v2/plans/${planId}/concepts/${concept.id}/quiz/flag`
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ question_text: questionText }),
      })
      if (response.ok) {
        setFlaggedQuestions((prev) => ({ ...prev, [index]: true }))
      } else {
        alert('Failed to flag question.')
      }
    } catch (err) {
      console.error('Flag error:', err)
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
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Detailed Explanation
              </h3>
              <div className="space-y-3.5">
                {parseExplanationSections(content.explanation).map((section, idx) => (
                  <div
                    key={idx}
                    className={`rounded-xl border p-4 leading-relaxed text-xs space-y-1.5 transition duration-200 hover:scale-[1.01] ${section.style}`}
                  >
                    <div className="flex items-center gap-1.5 font-bold text-[9px] uppercase tracking-wider">
                      <span>{section.icon}</span>
                      <span>{section.title}</span>
                    </div>
                    <p className="text-slate-350 leading-relaxed whitespace-pre-wrap">
                      {section.content.replace(/^[:\s\-*]+/g, '').trim()}
                    </p>
                  </div>
                ))}
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
                      {resource.platform && resource.query ? (
                        <p className="text-[10px] text-slate-500 truncate">
                          Search <span className="text-violet-400 font-bold">{resource.platform}</span>: <span className="text-slate-400 italic">"{resource.query}"</span>
                        </p>
                      ) : (
                        <p className="text-[10px] text-slate-500 truncate">
                          {new URL(resource.url).hostname}
                        </p>
                      )}
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
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex justify-between items-center">
              <span>Concept Checkpoints</span>
              <span className="text-[10px] text-slate-500 lowercase normal-case">Grade instant objective MCQ checks</span>
            </h3>
            {content.quiz.map((q, index) => {
              const selectedIdx = selectedOptions[index];
              const confidenceVal = selectedConfidence[index];
              const isGraded = !!gradingResults[index];
              const isLdg = !!gradingLoading[index];
              const gradeRes = gradingResults[index];
              const isFlagged = !!flaggedQuestions[index];

              return (
                <div key={index} className="rounded-xl border border-slate-900 bg-slate-900/30 p-4 space-y-4 relative overflow-hidden">
                  {/* Flag button */}
                  <button
                    type="button"
                    onClick={() => handleFlagQuestion(index, q.question)}
                    disabled={isFlagged}
                    className={`absolute top-4 right-4 text-[10px] font-bold px-2 py-0.5 rounded-md border transition duration-150 ${
                      isFlagged
                        ? 'border-violet-500/20 bg-violet-500/10 text-violet-400'
                        : 'border-slate-800 text-slate-500 hover:text-slate-350 hover:border-slate-700'
                    }`}
                  >
                    {isFlagged ? '🏳️ Flagged' : '🏳️ Flag Question'}
                  </button>

                  <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-md">
                    Q{index + 1}: Multiple Choice
                  </span>
                  <p className="text-sm font-semibold text-slate-200 leading-snug pr-20">{q.question}</p>
                  
                  {/* Options List */}
                  <div className="grid gap-2 mt-2">
                    {q.options.map((option, optIdx) => {
                      const isSelected = selectedIdx === optIdx;
                      
                      // Highlight styles when graded
                      let buttonStyle = 'border-slate-800 text-slate-400 bg-slate-950/40 hover:border-slate-700 hover:text-slate-200';
                      if (isGraded) {
                        const isCorrectOpt = optIdx === q.correct_option_index;
                        if (isCorrectOpt) {
                          buttonStyle = 'border-emerald-500 bg-emerald-500/10 text-emerald-300 font-medium cursor-default';
                        } else if (isSelected) {
                          buttonStyle = 'border-rose-500 bg-rose-500/10 text-rose-300 font-medium cursor-default';
                        } else {
                          buttonStyle = 'border-slate-900 text-slate-600 bg-slate-950/25 cursor-default';
                        }
                      } else if (isSelected) {
                        buttonStyle = 'border-violet-500 bg-violet-500/10 text-violet-300 font-medium';
                      }

                      return (
                        <button
                          key={optIdx}
                          type="button"
                          disabled={isGraded}
                          onClick={() =>
                            setSelectedOptions((prev) => ({ ...prev, [index]: optIdx }))
                          }
                          className={`block w-full rounded-xl border px-3.5 py-2.5 text-left text-xs transition duration-150 ${buttonStyle}`}
                        >
                          {option}
                        </button>
                      );
                    })}
                  </div>

                  {/* Confidence Slider / Selection */}
                  {selectedIdx !== undefined && !isGraded && (
                    <div className="space-y-3.5 pt-2 border-t border-slate-900 animate-fadeIn">
                      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        How sure were you of this answer?
                      </p>
                      <div className="grid grid-cols-3 gap-2 bg-slate-950/80 p-1 border border-slate-900 rounded-xl">
                        {[
                          { label: '😰 Just guessing', val: 0.25 },
                          { label: '🤔 Somewhat sure', val: 0.5 },
                          { label: '💪 Very confident', val: 1.0 },
                        ].map((conf) => (
                          <button
                            key={conf.val}
                            type="button"
                            onClick={() =>
                              setSelectedConfidence((prev) => ({ ...prev, [index]: conf.val }))
                            }
                            className={`py-2 text-[10px] font-semibold rounded-lg transition text-center ${
                              confidenceVal === conf.val
                                ? 'bg-violet-600 text-white shadow-md font-bold'
                                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
                            }`}
                          >
                            {conf.label}
                          </button>
                        ))}
                      </div>

                      {/* Submit action */}
                      {confidenceVal !== undefined && (
                        <button
                          type="button"
                          disabled={isLdg}
                          onClick={() => handleGradeQuiz(index, selectedIdx, confidenceVal)}
                          className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-800 text-white disabled:text-slate-500 font-bold text-xs rounded-xl shadow-lg shadow-violet-900/10 transition"
                        >
                          {isLdg ? 'Submitting & Grading...' : 'Submit Answer'}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Grading results display */}
                  {isGraded && gradeRes && (
                    <div className={`p-3.5 rounded-xl border leading-relaxed text-xs space-y-2 animate-fadeIn ${
                      gradeRes.correct
                        ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-300'
                        : 'border-rose-500/20 bg-rose-500/5 text-rose-350'
                    }`}>
                      <div className="flex justify-between items-center font-bold">
                        <span>{gradeRes.correct ? '✅ Answer Correct' : '❌ Answer Incorrect'}</span>
                        <span className="bg-white/10 px-2 py-0.5 rounded text-[9px]">
                          Mastery Delta Calculated
                        </span>
                      </div>
                      <p className="text-slate-350 leading-relaxed font-medium">{gradeRes.feedback}</p>
                    </div>
                  )}
                </div>
              );
            })}
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
