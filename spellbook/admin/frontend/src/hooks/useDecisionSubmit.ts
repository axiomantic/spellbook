import { useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type {
  CanvasDecisionSubmit,
  SubmitRequest,
} from '../canvas/CanvasDecisionContext'

/**
 * Decision-submit mutation (design §8.2), instantiated in `CanvasDetail`
 * and exposed through `CanvasDecisionContext` so it survives shortcode
 * remounts (RT-6).
 *
 * Posts to `/api/canvas/{name}/decision/submit` with
 * `suppressAuthReload: true` (§8.4) so a 401 throws a coded `auth_expired`
 * error the control can render, instead of `fetchApi` reloading the page.
 *
 * `lastFreeText` is derived from the last submitted body's `free_text`
 * (React Query `mutation.variables`), giving the local free-text echo a
 * remount-safe home (RT-3) — the note is never round-tripped from the
 * server (§8.3).
 */
export function useDecisionSubmit(name: string): CanvasDecisionSubmit {
  const m = useMutation({
    mutationFn: (body: SubmitRequest) =>
      fetchApi(`/api/canvas/${encodeURIComponent(name)}/decision/submit`, {
        method: 'POST',
        body,
        suppressAuthReload: true,
      }),
  })
  // Memoize the projected return so its identity only changes when an
  // observable field does. Without this, every CanvasDetail render produces a
  // fresh object, which would force the memoized provider value (M3) and every
  // shortcode consumer to re-render needlessly.
  return useMemo<CanvasDecisionSubmit>(
    () => ({
      mutate: m.mutate,
      status: m.status,
      error: (m.error as (Error & { code?: string }) | null) ?? null,
      lastFreeText: m.variables?.free_text ?? null,
    }),
    [m.mutate, m.status, m.error, m.variables],
  )
}
