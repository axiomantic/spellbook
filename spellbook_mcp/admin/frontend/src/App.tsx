import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { AppShell } from './components/layout/AppShell'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Login } from './pages/Login'
import { ConfigEditor } from './pages/ConfigEditor'
import Dashboard from './pages/Dashboard'
import { MemoryBrowser } from './pages/MemoryBrowser'
import { SecurityLog } from './pages/SecurityLog'
import { Sessions } from './pages/Sessions'
import { FractalExplorer } from './pages/FractalExplorer'

function AuthGate() {
  const { authenticated, checking } = useAuth()

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
        <span className="font-mono text-xs uppercase tracking-widest text-[#5a5650]">
          // CHECKING SESSION...
        </span>
      </div>
    )
  }

  if (!authenticated) {
    return <Login />
  }

  return (
    <BrowserRouter basename="/admin">
      <AppShell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/memory" element={<MemoryBrowser />} />
          <Route path="/security" element={<SecurityLog />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/config" element={<ConfigEditor />} />
          <Route path="/fractal" element={<FractalExplorer />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
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
