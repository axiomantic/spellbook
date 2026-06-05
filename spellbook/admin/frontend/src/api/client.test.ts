import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchApi } from './client'

/**
 * Tests for the §8.4 / finding #2 `suppressAuthReload` opt-out on the 401 path.
 *
 * Default behavior MUST be byte-for-byte unchanged for every existing caller:
 * a 401 calls `window.location.reload()` then throws. The decision-submit
 * mutation passes `suppressAuthReload: true` so the control can render the
 * `auth_error` state and drive a controlled re-auth UX instead of an
 * unconditional reload.
 */
describe('fetchApi suppressAuthReload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('default 401 calls window.location.reload exactly once and throws "Session expired"', async () => {
    const reload = vi.fn()
    vi.stubGlobal('window', {
      location: { reload },
    } as unknown as Window & typeof globalThis)
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 401 })),
    )

    let caught: Error | null = null
    try {
      await fetchApi('/x', { method: 'POST' })
    } catch (e) {
      caught = e as Error
    }
    expect(caught).not.toBeNull()
    expect(caught!.message).toBe('Session expired')
    expect((caught as Error & { code?: string }).code).toBeUndefined()
    expect(reload).toHaveBeenCalledTimes(1)
    expect(reload).toHaveBeenCalledWith()
  })

  it('suppressAuthReload=true throws coded auth_expired error without reloading', async () => {
    const reload = vi.fn()
    vi.stubGlobal('window', {
      location: { reload },
    } as unknown as Window & typeof globalThis)
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 401 })),
    )

    let caught: (Error & { code?: string }) | null = null
    try {
      await fetchApi('/x', { method: 'POST', suppressAuthReload: true })
    } catch (e) {
      caught = e as Error & { code?: string }
    }
    expect(reload).toHaveBeenCalledTimes(0)
    expect(caught).not.toBeNull()
    expect(caught!.message).toBe('Admin session expired')
    expect(caught!.code).toBe('auth_expired')
  })
})
