import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import { getDueReviews, reviewConcept } from '../api/client'
import type { DueReviewItem } from '../types'

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

export default function ReviewDeck() {
  const { id } = useParams<{ id: string }>()
  const { getToken, isLoaded } = useAuth()

  const [cards, setCards] = useState<DueReviewItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Card view state
  const [isFlipped, setIsFlipped] = useState(false)
  const [selectedOptions, setSelectedOptions] = useState<Record<number, number>>({})

  useEffect(() => {
    if (!isLoaded) return
    if (!id) return

    const fetchDueCards = async () => {
      try {
        setLoading(true)
        const token = await getToken()
        const data = await getDueReviews(id, token)
        setCards(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch due concepts')
      } finally {
        setLoading(false)
      }
    }

    fetchDueCards()
  }, [id, isLoaded, getToken])

  const handleRate = async (rating: number) => {
    if (!id || cards.length === 0) return
    const activeCard = cards[currentIndex]

    try {
      const token = await getToken()
      await reviewConcept(id, activeCard.id, rating, token)
      
      // Satisfying transition: flip back first, clear states, then change card
      setIsFlipped(false)
      setSelectedOptions({})
      
      setTimeout(() => {
        if (currentIndex < cards.length - 1) {
          setCurrentIndex(prev => prev + 1)
        } else {
          // Finished all due cards!
          setCards([])
          setCurrentIndex(0)
        }
      }, 300)

    } catch (err) {
      alert('Failed to save review. Please try again.')
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <div className="w-12 h-12 border-4 border-violet-500/20 border-t-violet-500 rounded-full animate-spin mb-4" />
        <p className="text-slate-400 text-sm animate-pulse">Loading review queue...</p>
      </div>
    )
  }

  if (error || !id) {
    return (
      <div className="text-center py-12">
        <p className="text-rose-450">{error ?? 'Plan ID not found'}</p>
        <Link to="/" className="mt-4 inline-block text-sm text-violet-400 hover:underline">
          Return to home
        </Link>
      </div>
    )
  }

  if (cards.length === 0) {
    return (
      <div className="mx-auto max-w-xl text-center py-16 bg-slate-900/40 border border-slate-900 rounded-3xl p-8 relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-emerald-500/5 rounded-full blur-3xl animate-pulse" />
        <span className="text-5xl block mb-6 animate-bounce">🎉</span>
        <h2 className="text-2xl font-bold text-white mb-2">All Caught Up!</h2>
        <p className="text-slate-400 text-sm max-w-md mx-auto mb-8">
          There are no concepts due for review in this plan right now. Spaced repetition will schedule next review times based on your scores.
        </p>
        <Link
          to={`/plan/${id}`}
          className="px-5 py-3 bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition duration-200"
        >
          Return to Concept Map
        </Link>
      </div>
    )
  }

  const activeCard = cards[currentIndex]

  return (
    <div className="mx-auto max-w-xl relative">
      {/* Dynamic ambient background highlights */}
      <div className="absolute -top-24 -left-24 w-72 h-72 bg-violet-600/10 rounded-full blur-[80px]" />
      <div className="absolute -bottom-24 -right-24 w-72 h-72 bg-indigo-650/10 rounded-full blur-[80px]" />

      <div className="flex justify-between items-center mb-6 relative z-10">
        <div>
          <Link to={`/plan/${id}`} className="text-xs text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-1">
            &larr; Back to study plan
          </Link>
          <h1 className="text-2xl font-extrabold text-white mt-1">Review Deck</h1>
        </div>
        <span className="bg-slate-900 border border-slate-800 text-slate-300 font-bold px-3 py-1 rounded-xl text-xs">
          Card {currentIndex + 1} of {cards.length}
        </span>
      </div>

      {/* Main Flashcard Container */}
      <div className="relative z-10 bg-slate-900 border border-slate-850 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 min-h-[360px] flex flex-col justify-between">
        
        {/* Card Front Side (Concept Question/Name) */}
        {!isFlipped ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center space-y-4 py-8">
            <span className="text-xs uppercase font-bold tracking-widest text-violet-450 bg-violet-500/10 px-3 py-1 rounded-full">
              Recall Challenge
            </span>
            <h2 className="text-3xl font-extrabold text-white tracking-tight px-4 leading-tight">
              {activeCard.name}
            </h2>
            <p className="text-slate-400 text-sm max-w-xs leading-relaxed">
              {activeCard.description || 'Explain this concept to yourself, then reveal the resources to test your knowledge.'}
            </p>
            
            <button
              onClick={() => setIsFlipped(true)}
              className="mt-8 px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition duration-200"
            >
              Reveal explanation & Quiz
            </button>
          </div>
        ) : (
          /* Card Back Side (Explanation, Quiz, resources) */
          <div className="flex-1 space-y-6 overflow-y-visible animate-fadeIn">
            {/* Explanation callout sections */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                Detailed Explanation
              </h3>
              <div className="space-y-3">
                {parseExplanationSections(activeCard.explanation).map((section, idx) => (
                  <div
                    key={idx}
                    className={`rounded-2xl border p-4 leading-relaxed text-xs space-y-1.5 transition ${section.style}`}
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
            </div>

            {/* Quiz questions */}
            {activeCard.quiz.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
                  Quick Quiz Review
                </h3>
                <div className="space-y-4">
                  {activeCard.quiz.map((q, idx) => {
                    const selectedIdx = selectedOptions[idx];
                    const isAnswered = selectedIdx !== undefined;

                    return (
                      <div key={idx} className="rounded-2xl border border-slate-850 bg-slate-950/80 p-4 space-y-2">
                        <span className="text-[9px] font-bold uppercase tracking-wider text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-md">
                          Checkpoint MCQ
                        </span>
                        <p className="text-sm text-slate-200">{q.question}</p>
                        
                        <div className="mt-3 space-y-2">
                          {q.options.map((opt, optIdx) => {
                            const isSelected = selectedIdx === optIdx;
                            
                            let btnStyle = 'border-slate-850 text-slate-400 hover:border-slate-700';
                            if (isAnswered) {
                              const isCorrect = optIdx === q.correct_option_index;
                              if (isCorrect) {
                                btnStyle = 'border-emerald-500 bg-emerald-500/10 text-emerald-300';
                              } else if (isSelected) {
                                btnStyle = 'border-rose-500 bg-rose-500/10 text-rose-300';
                              } else {
                                btnStyle = 'border-slate-950 text-slate-650';
                              }
                            } else if (isSelected) {
                              btnStyle = 'border-violet-500 bg-violet-500/10 text-violet-300';
                            }

                            return (
                              <button
                                key={opt}
                                type="button"
                                disabled={isAnswered}
                                onClick={() => setSelectedOptions(prev => ({ ...prev, [idx]: optIdx }))}
                                className={`block w-full rounded-xl border px-3 py-2 text-left text-sm transition ${btnStyle}`}
                              >
                                {opt}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Resources link list */}
            {activeCard.resources.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2.5">
                  Resources for reference
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {activeCard.resources.map((res) => (
                    <a
                      key={res.url}
                      href={res.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 px-3 py-2.5 bg-slate-950/40 border border-slate-850 hover:border-violet-500/50 hover:bg-slate-950 rounded-xl text-xs text-slate-300 truncate"
                    >
                      <span>
                        {res.type === 'video' ? '🎬' : res.type === 'docs' ? '📄' : '📰'}
                      </span>
                      <span className="truncate">{res.title}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Self-Grading Controller Panel */}
        {isFlipped && (
          <div className="border-t border-slate-850 pt-6 space-y-3">
            <p className="text-xs text-center font-bold tracking-wider text-slate-500 uppercase">
              How well did you recall this concept?
            </p>
            <div className="grid grid-cols-5 gap-1 bg-slate-950 p-1.5 rounded-2xl border border-slate-850">
              <button
                onClick={() => handleRate(1)}
                className="flex flex-col items-center justify-center py-2.5 rounded-xl hover:bg-rose-500/10 text-rose-500 font-bold transition duration-200 group"
                title="Forgot completely"
              >
                <span className="text-lg group-hover:scale-110 transition">1</span>
                <span className="text-[8px] uppercase tracking-wider mt-0.5 opacity-60">Forgot</span>
              </button>
              <button
                onClick={() => handleRate(2)}
                className="flex flex-col items-center justify-center py-2.5 rounded-xl hover:bg-amber-500/10 text-amber-500 font-bold transition duration-200 group"
                title="Partially recalled"
              >
                <span className="text-lg group-hover:scale-110 transition">2</span>
                <span className="text-[8px] uppercase tracking-wider mt-0.5 opacity-60">Hard</span>
              </button>
              <button
                onClick={() => handleRate(3)}
                className="flex flex-col items-center justify-center py-2.5 rounded-xl hover:bg-yellow-500/10 text-yellow-500 font-bold transition duration-200 group"
                title="Recalled with effort"
              >
                <span className="text-lg group-hover:scale-110 transition">3</span>
                <span className="text-[8px] uppercase tracking-wider mt-0.5 opacity-60">OK</span>
              </button>
              <button
                onClick={() => handleRate(4)}
                className="flex flex-col items-center justify-center py-2.5 rounded-xl hover:bg-indigo-500/10 text-indigo-400 font-bold transition duration-200 group"
                title="Recalled easily"
              >
                <span className="text-lg group-hover:scale-110 transition">4</span>
                <span className="text-[8px] uppercase tracking-wider mt-0.5 opacity-60">Easy</span>
              </button>
              <button
                onClick={() => handleRate(5)}
                className="flex flex-col items-center justify-center py-2.5 rounded-xl hover:bg-emerald-500/10 text-emerald-400 font-bold transition duration-200 group"
                title="Perfect recall"
              >
                <span className="text-lg group-hover:scale-110 transition">5</span>
                <span className="text-[8px] uppercase tracking-wider mt-0.5 opacity-60">Perfect</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
