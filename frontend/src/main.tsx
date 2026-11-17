import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/clerk-react'
import './index.css'
import App from './App.tsx'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

function MissingKeyBanner() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6">
      <div className="max-w-md w-full bg-slate-900 border border-violet-500/30 rounded-2xl p-6 shadow-2xl text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 flex items-center justify-center mx-auto text-2xl">
          🧠
        </div>
        <h2 className="text-xl font-bold text-white">Clerk Authentication Setup</h2>
        <p className="text-sm text-slate-400">
          To run Conceptra, configure your Clerk Publishable Key in <code className="text-violet-400 bg-slate-800 px-1.5 py-0.5 rounded text-xs">frontend/.env.local</code>:
        </p>
        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-left text-xs font-mono text-slate-300">
          VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
        </div>
        <p className="text-xs text-slate-500">
          Get your free API key at <a href="https://dashboard.clerk.com" target="_blank" rel="noreferrer" className="text-violet-400 underline hover:text-violet-300">dashboard.clerk.com</a>.
        </p>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {PUBLISHABLE_KEY ? (
      <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
        <App />
      </ClerkProvider>
    ) : (
      <MissingKeyBanner />
    )}
  </StrictMode>,
)
