import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'

interface AuthState {
  authenticated: boolean
  checking: boolean
  login: (password: string) => Promise<string | null>
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  authenticated: false,
  checking: true,
  login: async () => 'Not initialized',
  logout: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    fetch('/admin/api/auth/check', { credentials: 'same-origin' })
      .then(res => {
        setAuthenticated(res.ok)
        setChecking(false)
      })
      .catch(() => {
        setAuthenticated(false)
        setChecking(false)
      })
  }, [])

  const login = useCallback(async (password: string): Promise<string | null> => {
    try {
      const res = await fetch('/admin/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setAuthenticated(true)
        return null
      }
      return 'Invalid password'
    } catch {
      return 'Connection failed'
    }
  }, [])

  const logout = useCallback(() => {
    fetch('/admin/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    }).finally(() => setAuthenticated(false))
  }, [])

  return (
    <AuthContext.Provider value={{ authenticated, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
