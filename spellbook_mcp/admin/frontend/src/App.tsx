import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { AppShell } from './components/layout/AppShell'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter basename="/admin">
        <AppShell>
          <Routes>
            <Route path="/" element={<div className="p-8"><h1 className="text-2xl font-sans">// DASHBOARD</h1><p className="text-text-secondary mt-2">Coming soon.</p></div>} />
            <Route path="/memory" element={<div className="p-8"><h1 className="text-2xl font-sans">// MEMORY</h1></div>} />
            <Route path="/security" element={<div className="p-8"><h1 className="text-2xl font-sans">// SECURITY</h1></div>} />
            <Route path="/sessions" element={<div className="p-8"><h1 className="text-2xl font-sans">// SESSIONS</h1></div>} />
            <Route path="/config" element={<div className="p-8"><h1 className="text-2xl font-sans">// CONFIG</h1></div>} />
            <Route path="/fractal" element={<div className="p-8"><h1 className="text-2xl font-sans">// FRACTAL</h1></div>} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
