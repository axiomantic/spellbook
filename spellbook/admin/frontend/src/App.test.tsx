import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock react-router-dom to use MemoryRouter instead of BrowserRouter
// This lets us control the initial route in tests
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    BrowserRouter: ({ children }: { children: React.ReactNode }) => {
      // Use MemoryRouter with a configurable initial entry
      const { MemoryRouter } = actual as typeof import('react-router-dom')
      return (
        <MemoryRouter initialEntries={[currentRoute]}>
          {children}
        </MemoryRouter>
      )
    },
    useNavigate: () => mockNavigate,
  }
})

// Mock auth to always be authenticated
vi.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ authenticated: true, checking: false }),
}))

// Mock WebSocket provider
vi.mock('./contexts/WebSocketContext', () => ({
  WebSocketProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock AppShell to just render children
vi.mock('./components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="app-shell">{children}</div>,
}))

// Mock all page components to simple identifiable elements
vi.mock('./pages/Dashboard', () => ({
  default: () => <div data-testid="dashboard-page">Dashboard</div>,
}))
vi.mock('./pages/MemoryBrowser', () => ({
  MemoryBrowser: () => <div data-testid="memory-page">Memory</div>,
}))
vi.mock('./pages/SecurityLog', () => ({
  SecurityLog: () => <div data-testid="security-page">Security</div>,
}))
vi.mock('./pages/Sessions', () => ({
  Sessions: () => <div data-testid="sessions-page">Sessions</div>,
}))
vi.mock('./pages/SessionDetailPage', () => ({
  SessionDetailPage: () => <div data-testid="session-detail-page">SessionDetail</div>,
}))
vi.mock('./pages/ChatHistoryPage', () => ({
  ChatHistoryPage: () => <div data-testid="chat-page">Chat</div>,
}))
vi.mock('./pages/FractalExplorer', () => ({
  FractalExplorer: () => <div data-testid="fractal-page">Fractal</div>,
}))
vi.mock('./pages/AnalyticsPage', () => ({
  AnalyticsPage: () => <div data-testid="analytics-page">Analytics</div>,
}))
vi.mock('./pages/HealthPage', () => ({
  HealthPage: () => <div data-testid="health-page">Health</div>,
}))
vi.mock('./pages/EventMonitorPage', () => ({
  EventMonitorPage: () => <div data-testid="events-page">Events</div>,
}))
vi.mock('./pages/ConfigEditor', () => ({
  ConfigEditor: () => <div data-testid="config-page">Config</div>,
}))
vi.mock('./pages/Login', () => ({
  Login: () => <div data-testid="login-page">Login</div>,
}))
vi.mock('./components/shared/ErrorBoundary', () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock the page components we expect to be added
vi.mock('./pages/StacksPage', () => ({
  StacksPage: () => <div data-testid="stacks-page">StacksPage</div>,
}))
vi.mock('./pages/CorrectionsPage', () => ({
  CorrectionsPage: () => <div data-testid="corrections-page">CorrectionsPage</div>,
}))
vi.mock('./pages/FocusPage', () => ({
  FocusPage: () => <div data-testid="focus-page">FocusPage</div>,
}))

// Variable to control the initial route for each test
let currentRoute = '/'

import App from './App'

describe('App routing after FocusPage split', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentRoute = '/'
  })

  it('renders StacksPage at /stacks', () => {
    currentRoute = '/stacks'
    render(<App />)

    expect(screen.getByTestId('stacks-page')).toBeInTheDocument()
    expect(screen.getByText('StacksPage')).toBeInTheDocument()
  })

  it('renders CorrectionsPage at /corrections', () => {
    currentRoute = '/corrections'
    render(<App />)

    expect(screen.getByTestId('corrections-page')).toBeInTheDocument()
    expect(screen.getByText('CorrectionsPage')).toBeInTheDocument()
  })

  it('redirects /focus to /stacks', () => {
    currentRoute = '/focus'
    render(<App />)

    // After redirect, StacksPage should render (not FocusPage)
    expect(screen.getByTestId('stacks-page')).toBeInTheDocument()
    expect(screen.queryByTestId('focus-page')).not.toBeInTheDocument()
  })

  it('does not render FocusPage at /focus', () => {
    currentRoute = '/focus'
    render(<App />)

    expect(screen.queryByTestId('focus-page')).not.toBeInTheDocument()
  })
})
