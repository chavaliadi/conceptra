import { useState, useRef } from 'react'
import type { FormEvent, DragEvent, ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@clerk/clerk-react'
import { createPlan, uploadSyllabus } from '../api/client'

function defaultExamDate(): string {
  const date = new Date()
  date.setDate(date.getDate() + 21)
  return date.toISOString().split('T')[0]
}

const loadingSteps = [
  'Extracting core concepts from curriculum...',
  'Assembling dependency graph edges...',
  'Optimizing topological study calendar...',
  'Synthesizing explanation & resource guides...'
]

export default function Landing() {
  const navigate = useNavigate()
  const { getToken } = useAuth()
  const [inputMode, setInputMode] = useState<'topic' | 'pdf'>('topic')
  const [topic, setTopic] = useState('')

  // PDF upload states
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [examDate, setExamDate] = useState(defaultExamDate)
  const [hoursPerDay, setHoursPerDay] = useState(2)
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState<string | null>(null)

  // Drag and drop handlers
  function handleDrag(e: DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      if (file.type === "application/pdf" || file.name.endsWith('.pdf')) {
        setPdfFile(file)
        setError(null)
      } else {
        setError("Only PDF files are supported")
      }
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      setPdfFile(e.target.files[0])
      setError(null)
    }
  }

  function triggerFileInput() {
    fileInputRef.current?.click()
  }

  function clearFile(e: FormEvent) {
    e.stopPropagation()
    setPdfFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    let finalTopic = topic.trim()
    if (inputMode === 'pdf') {
      if (!pdfFile) {
        setError('Please upload a syllabus PDF first.')
        return
      }
    } else {
      if (!finalTopic) {
        setError('Please provide a topic.')
        return
      }
    }

    setLoading(true)
    setLoadingStep(0)

    try {
      const token = await getToken()
      // Initiate API call based on input mode
      let response
      if (inputMode === 'pdf' && pdfFile) {
        response = await uploadSyllabus(pdfFile, examDate, hoursPerDay, token)
      } else {
        response = await createPlan({
          topic: finalTopic,
          exam_date: examDate,
          hours_per_day: hoursPerDay,
        }, token)
      }

      // Simulate visually premium sequential loading steps for Phase 1
      for (let step = 0; step < loadingSteps.length; step++) {
        setLoadingStep(step)
        await new Promise((resolve) => setTimeout(resolve, 900))
      }

      navigate(`/plan/${response.id}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create plan'
      if (msg.includes('NON_SEARCHABLE_PDF')) {
        setError("This PDF doesn't contain selectable text. Please upload a searchable PDF.")
      } else {
        setError(msg)
      }
      setLoading(false)
    }
  }

  const isSubmitDisabled = loading || (inputMode === 'topic' ? !topic.trim() : !pdfFile)

  if (loading) {
    return (
      <div className="mx-auto max-w-xl flex flex-col items-center justify-center min-h-[50vh] text-center p-8 bg-slate-900/40 backdrop-blur-md rounded-3xl border border-slate-800/80 shadow-2xl relative overflow-hidden">
        {/* Decorative ambient glowing backdrops */}
        <div className="absolute -top-40 -left-40 w-80 h-80 bg-violet-600/10 rounded-full blur-[100px]" />
        <div className="absolute -bottom-40 -right-40 w-80 h-80 bg-fuchsia-600/10 rounded-full blur-[100px]" />

        {/* Loading ring */}
        <div className="relative flex items-center justify-center w-24 h-24 mb-8">
          <div className="absolute w-20 h-20 border-4 border-violet-500/20 rounded-full" />
          <div className="absolute w-20 h-20 border-4 border-transparent border-t-violet-500 border-r-fuchsia-500 rounded-full animate-spin" />
          <span className="text-xl">🧠</span>
        </div>

        {/* Text and percentages */}
        <h2 className="text-2xl font-bold tracking-tight text-white mb-2">Generating Study Plan</h2>
        <div className="min-h-[2.5rem] flex items-center justify-center">
          <p className="text-violet-400 font-medium text-lg animate-pulse">
            {loadingSteps[loadingStep]}
          </p>
        </div>

        {/* Dynamic step indicators */}
        <div className="flex gap-2.5 mt-8 w-full max-w-[200px] justify-center">
          {loadingSteps.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-500 ${i <= loadingStep ? 'w-8 bg-violet-500' : 'w-2 bg-slate-800'
                }`}
            />
          ))}
        </div>

        <p className="mt-8 text-xs text-slate-500 uppercase tracking-widest">
          Assembling concept dependency graph
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-xl relative">
      {/* Background radial highlight */}
      <div className="absolute -top-24 -left-24 w-72 h-72 bg-violet-600/15 rounded-full blur-[80px]" />
      <div className="absolute -bottom-24 -right-24 w-72 h-72 bg-fuchsia-600/10 rounded-full blur-[80px]" />

      <div className="mb-10 text-center relative z-10">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
          Turn any topic into a{' '}
          <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
            study plan
          </span>
        </h1>
        <p className="mt-4 text-slate-400 text-base sm:text-lg">
          Paste a subject or upload a syllabus PDF. Get an interactive concept dependency map, scheduled timeline, and practice content instantly.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-3xl border border-slate-800/80 bg-slate-900/65 backdrop-blur-md p-6 sm:p-8 shadow-2xl relative z-10"
      >
        {/* Input Mode Selector Tabs */}
        <div>
          <label className="mb-2.5 block text-xs font-semibold uppercase tracking-wider text-slate-400">
            Study Source
          </label>
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-950 p-1">
            <button
              type="button"
              onClick={() => setInputMode('topic')}
              className={`rounded-lg py-2 text-sm font-medium transition ${inputMode === 'topic'
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              📝 Text Topic
            </button>
            <button
              type="button"
              onClick={() => setInputMode('pdf')}
              className={`rounded-lg py-2 text-sm font-medium transition ${inputMode === 'pdf'
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              📁 Syllabus PDF
            </button>
          </div>
        </div>

        {/* Dynamic Source Input */}
        {inputMode === 'topic' ? (
          <div>
            <label htmlFor="topic" className="mb-2 block text-sm font-medium text-slate-300">
              Topic Name
            </label>
            <input
              id="topic"
              type="text"
              required={inputMode === 'topic'}
              placeholder='e.g. "Operating Systems" or "React Fundamentals"'
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 transition duration-200"
            />
          </div>
        ) : (
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-300">
              Upload Syllabus PDF
            </label>

            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf"
              onChange={handleFileChange}
              className="hidden"
            />

            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={triggerFileInput}
              className={`flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-6 cursor-pointer transition duration-300 ${dragActive
                  ? 'border-violet-500 bg-violet-500/5'
                  : 'border-slate-800 hover:border-slate-700 bg-slate-950/50 hover:bg-slate-950/80'
                }`}
            >
              {pdfFile ? (
                <div className="flex items-center gap-3 w-full max-w-xs justify-between rounded-xl bg-slate-900 border border-slate-800 px-4 py-3">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <span className="text-xl shrink-0">📄</span>
                    <span className="text-sm text-slate-200 truncate font-medium">{pdfFile.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={clearFile}
                    className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
                    aria-label="Remove file"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-3xl mb-3">📥</div>
                  <p className="text-sm font-medium text-slate-300">Drag & drop your syllabus PDF here</p>
                  <p className="text-xs text-slate-500 mt-1">or click to browse from files</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Date and Hours parameters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="exam-date" className="mb-2 block text-sm font-medium text-slate-300">
              Exam Date
            </label>
            <input
              id="exam-date"
              type="date"
              required
              value={examDate}
              min={new Date().toISOString().split('T')[0]}
              onChange={(e) => setExamDate(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-white focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 transition duration-200"
            />
          </div>

          <div>
            <label htmlFor="hours" className="mb-2 flex justify-between text-sm font-medium text-slate-300">
              <span>Study Hours / Day</span>
              <span className="text-violet-400 font-bold bg-violet-400/10 px-2 py-0.5 rounded-md text-xs">{hoursPerDay} hours</span>
            </label>
            <div className="flex items-center h-12">
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
          </div>
        </div>

        {/* Error reporting */}
        {error && (
          <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3.5 text-sm text-rose-300 animate-shake">
            ⚠️ {error}
          </p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-3.5 font-medium text-white shadow-lg shadow-violet-900/20 hover:shadow-violet-900/40 transition duration-300 hover:from-violet-500 hover:to-indigo-500 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100"
        >
          Generate study plan
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-slate-500 relative z-10">
        Try typing &quot;Operating Systems&quot; or &quot;React Fundamentals&quot; to test with fixture data instantly.
      </p>
    </div>
  )
}
