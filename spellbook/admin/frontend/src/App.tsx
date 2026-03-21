import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
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
import { SessionDetailPage } from './pages/SessionDetailPage'
import { ChatHistoryPage } from './pages/ChatHistoryPage'
import { FractalExplorer } from './pages/FractalExplorer'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { HealthPage } from './pages/HealthPage'
import { EventMonitorPage } from './pages/EventMonitorPage'
import { StacksPage } from './pages/StacksPage'
import { CorrectionsPage } from './pages/CorrectionsPage'

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
            <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
            <Route path="/memory" element={<ErrorBoundary><MemoryBrowser /></ErrorBoundary>} />
            <Route path="/security" element={<ErrorBoundary><SecurityLog /></ErrorBoundary>} />
            <Route path="/sessions" element={<ErrorBoundary><Sessions /></ErrorBoundary>} />
            <Route path="/sessions/:project/:id" element={<ErrorBoundary><SessionDetailPage /></ErrorBoundary>} />
            <Route path="/sessions/:project/:id/chat" element={<ErrorBoundary><ChatHistoryPage /></ErrorBoundary>} />
            <Route path="/analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
            <Route path="/health" element={<ErrorBoundary><HealthPage /></ErrorBoundary>} />
            <Route path="/events" element={<ErrorBoundary><EventMonitorPage /></ErrorBoundary>} />
            <Route path="/stacks" element={<ErrorBoundary><StacksPage /></ErrorBoundary>} />
            <Route path="/corrections" element={<ErrorBoundary><CorrectionsPage /></ErrorBoundary>} />
            <Route path="/focus" element={<Navigate to="/stacks" replace />} />
            <Route path="/config" element={<ErrorBoundary><ConfigEditor /></ErrorBoundary>} />
            <Route path="/fractal" element={<ErrorBoundary><FractalExplorer /></ErrorBoundary>} />
            <Route path="/fractal/:graphId" element={<ErrorBoundary><FractalExplorer /></ErrorBoundary>} />
            <Route path="/fractal/:graphId/:nodeId" element={<ErrorBoundary><FractalExplorer /></ErrorBoundary>} />
            <Route path="/fractal/:graphId/:nodeId/chat" element={<ErrorBoundary><FractalExplorer /></ErrorBoundary>} />
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
