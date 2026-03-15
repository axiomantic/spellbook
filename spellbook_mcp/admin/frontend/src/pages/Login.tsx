import { useState, FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'

export function Login() {
  const { login } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const err = await login(password)
    setLoading(false)
    if (err) {
      setError(err)
      setPassword('')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#060606]">
      <div className="w-full max-w-sm border border-[#2a2a2a] bg-[#101010] p-8">
        <div className="mb-6">
          <span className="font-mono text-xs uppercase tracking-widest text-[#8a8480]">
            // SPELLBOOK
          </span>
          <h1 className="mt-2 font-mono text-lg text-[#f0ebe4]">
            ADMIN
          </h1>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="mb-2 block font-mono text-xs uppercase tracking-widest text-[#8a8480]">
            // PASSWORD
          </label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoFocus
            className="mb-4 w-full border border-[#2a2a2a] bg-[#060606] px-3 py-2 font-mono text-sm text-[#f0ebe4] outline-none focus:border-[#b4f461]"
            placeholder="MCP token"
          />

          {error && (
            <p className="mb-4 font-mono text-xs text-[#f46161]">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full border border-[#b4f461] bg-transparent px-4 py-2 font-mono text-xs uppercase tracking-widest text-[#b4f461] hover:bg-[#b4f461] hover:text-[#060606] disabled:border-[#2a2a2a] disabled:text-[#8a8480] disabled:hover:bg-transparent"
          >
            {loading ? 'AUTHENTICATING...' : 'ENTER'}
          </button>
        </form>

        <p className="mt-6 font-mono text-xs text-[#8a8480]">
          Token location: ~/.local/spellbook/.mcp-token
        </p>
      </div>
    </div>
  )
}
