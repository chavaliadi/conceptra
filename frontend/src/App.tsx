import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import PlanView from './pages/PlanView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/plan/:id" element={<PlanView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
