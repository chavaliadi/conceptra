import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import PlanView from './pages/PlanView'
import Dashboard from './pages/Dashboard'
import ReviewDeck from './pages/ReviewDeck'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/plan/:id" element={<PlanView />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/plan/:id/review" element={<ReviewDeck />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
