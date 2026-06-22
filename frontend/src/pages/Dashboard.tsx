import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import { listPlans, deletePlan } from '../api/client'
import type { Plan } from '../types'

export default function Dashboard() {
  const { getToken, isSignedIn, isLoaded } = useAuth()
  const navigate = useNavigate()
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      navigate('/')
      return
    }

    const fetchPlans = async () => {
      try {
        setLoading(true)
        const token = await getToken()
        const data = await listPlans(token)
        setPlans(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch plans')
      } finally {
        setLoading(false)
      }
    }

    fetchPlans()
  }, [isLoaded, isSignedIn, navigate])

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (!window.confirm('Are you sure you want to delete this study plan?')) {
      return
    }

    try {
      const token = await getToken()
      if (token) {
        await deletePlan(id, token)
        setPlans(plans.filter((p) => p.id !== id))
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete plan')
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] py-12">
        <div className="w-12 h-12 border-4 border-violet-500/20 border-t-violet-500 rounded-full animate-spin mb-4" />
        <p className="text-slate-400 text-sm animate-pulse">Loading your dashboard...</p>
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Decorative ambient highlights */}
      <div className="absolute -top-24 -left-24 w-72 h-72 bg-violet-600/10 rounded-full blur-[80px]" />
      <div className="absolute -bottom-24 -right-24 w-72 h-72 bg-fuchsia-600/5 rounded-full blur-[80px]" />

      <div className="flex justify-between items-center mb-8 relative z-10">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            My Study Plans
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Access and manage your generated learning curricula.
          </p>
        </div>
        <Link
          to="/"
          className="px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition duration-200 shadow-md shadow-violet-900/20"
        >
          Create New Plan
        </Link>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-300 text-sm">
          ⚠️ {error}
        </div>
      )}

      {plans.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/40 border border-slate-900 rounded-3xl p-8 relative z-10">
          <span className="text-4xl block mb-4">📚</span>
          <h3 className="text-lg font-bold text-white mb-2">No Study Plans Yet</h3>
          <p className="text-slate-400 text-sm max-w-sm mx-auto mb-6">
            Generate your first study map by entering a topic name or uploading a syllabus PDF.
          </p>
          <Link
            to="/"
            className="inline-block px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs uppercase tracking-wider rounded-xl transition duration-200"
          >
            Get Started
          </Link>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 relative z-10">
          {plans.map((plan) => (
            <Link
              key={plan.id}
              to={`/plan/${plan.id}`}
              className="group flex flex-col justify-between p-6 rounded-2xl border border-slate-850 bg-slate-900/40 hover:bg-slate-900/80 hover:border-violet-500/50 transition duration-300 shadow-lg"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold text-white group-hover:text-violet-400 transition text-lg leading-tight line-clamp-2">
                    {plan.topic}
                  </h3>
                  <button
                    onClick={(e) => handleDelete(e, plan.id)}
                    className="p-1.5 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 transition"
                    title="Delete Plan"
                  >
                    🗑️
                  </button>
                </div>

                <div className="space-y-1.5 text-xs text-slate-400">
                  <div className="flex justify-between">
                    <span>Exam Date:</span>
                    <span className="text-slate-200 font-medium">
                      {plan.exam_date ? new Date(plan.exam_date).toLocaleDateString() : 'Not set'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Study Pacing:</span>
                    <span className="text-slate-200 font-medium">{plan.hours_per_day}h / day</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Created:</span>
                    <span className="text-slate-500">
                      {new Date(plan.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-850 flex items-center justify-between text-xs">
                <span className={`px-2 py-0.5 rounded-full font-bold uppercase tracking-wider text-[10px] ${
                  plan.status === 'completed' 
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                    : plan.status === 'generating'
                    ? 'bg-violet-500/10 text-violet-400 border border-violet-500/20 animate-pulse'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                }`}>
                  {plan.status}
                </span>
                <span className="text-violet-400 font-semibold group-hover:translate-x-1 transition duration-300">
                  Open Plan &rarr;
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
