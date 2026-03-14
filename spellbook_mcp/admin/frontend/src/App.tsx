import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { AppShell } from './components/layout/AppShell'
import { ConfigEditor } from './pages/ConfigEditor'
import Dashboard from './pages/Dashboard'
import { MemoryBrowser } from './pages/MemoryBrowser'
import { SecurityLog } from './pages/SecurityLog'
import { Sessions } from './pages/Sessions'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter basename="/admin">
        <AppShell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/memory" element={<MemoryBrowser />} />
            <Route path="/security" element={<SecurityLog />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/config" element={<ConfigEditor />} />
            <Route path="/fractal" element={<div className="p-8"><h1 className="text-2xl font-sans">// FRACTAL</h1></div>} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
