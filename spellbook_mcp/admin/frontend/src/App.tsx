import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { AppShell } from './components/layout/AppShell'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { WebSocketProvider } from './contexts/WebSocketContext'
import { Login } from './pages/Login'
import { ConfigEditor } from './pages/ConfigEditor'
import Dashboard from './pages/Dashboard'
import { MemoryBrowser } from './pages/MemoryBrowser'
import { SecurityLog } from './pages/SecurityLog'
import { Sessions } from './pages/Sessions'
import { FractalExplorer } from './pages/FractalExplorer'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { HealthPage } from './pages/HealthPage'
import { EventMonitorPage } from './pages/EventMonitorPage'
import { FocusPage } from './pages/FocusPage'

function AuthGate() {
  const { authenticated, checking } = useAuth()

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#060606]">
        <span className="font-mono text-xs uppercase tracking-widest text-[#8a8480]">
          // CHECKING SESSION...
        </span>
      </div>
    )
  }

  if (!authenticated) {
    return <Login />
  }

  return (
    <WebSocketProvider>
      <BrowserRouter basename="/admin">
        <AppShell>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/memory" element={<MemoryBrowser />} />
            <Route path="/security" element={<SecurityLog />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="/events" element={<EventMonitorPage />} />
            <Route path="/focus" element={<FocusPage />} />
            <Route path="/config" element={<ConfigEditor />} />
            <Route path="/fractal" element={<FractalExplorer />} />
            <Route path="/fractal/:graphId" element={<FractalExplorer />} />
            <Route path="/fractal/:graphId/:nodeId" element={<FractalExplorer />} />
            <Route path="/fractal/:graphId/:nodeId/chat" element={<FractalExplorer />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </WebSocketProvider>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AuthGate />
      </AuthProvider>
    </ErrorBoundary>
  )
}
