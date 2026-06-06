import { createContext, useContext } from 'react'

/**
 * Projected decision detail (== `project_decision_for_detail`, design §3.0).
 *
 * The browser only ever sees this projection: no `await_binding`, no
 * `free_text`. `options` is `null` for `approve` kind, a list for `choice`.
 */
export interface DecisionDetail {
  decision_id: string
  kind: 'choice' | 'approve'
  prompt: string
  options: { value: string; label: string }[] | null
  status: 'pending' | 'submitted' | 'consumed' | 'cancelled'
}

/**
 * POST body for `/api/canvas/{name}/decision/submit` (design §5.1).
 * `free_text` is the operator's optional note; it is sent to the server
 * (which keeps it on disk for the agent) but never round-tripped back to
 * the SPA — the submitting tab echoes its own copy locally (§8.3).
 */
export interface SubmitRequest {
  decision_id: string
  value: string
  free_text: string | null
}

/**
 * Hoisted submission state (design §8.1 / RT-6). Lives in `CanvasDetail`
 * above `CanvasRender`, so it survives the shortcode remount a content
 * invalidation triggers.
 */
export interface CanvasDecisionSubmit {
  mutate: (body: SubmitRequest) => void
  status: 'idle' | 'pending' | 'success' | 'error'
  error: (Error & { code?: string }) | null
  /** the operator's own typed text, kept client-side for local echo (RT-3) */
  lastFreeText: string | null
}

export interface CanvasDecisionValue {
  canvasName: string
  decision: DecisionDetail | null
  submit: CanvasDecisionSubmit
  /**
   * Controlled re-auth trigger (design §8.4 / D1). On an `auth_expired`
   * submission error the leaf control renders a truthful banner plus an
   * explicit "Reauthenticate" button; clicking it invokes this handler, which
   * reloads through the existing login/handoff flow. Hoisted to the decision
   * context so `Choice` and `Approve` share one implementation instead of each
   * reaching for `window.location` directly.
   */
  reauthenticate: () => void
}

export const CanvasDecisionContext = createContext<CanvasDecisionValue | null>(null)

/**
 * Read the canvas decision context. Throws if a shortcode is rendered
 * outside `CanvasDecisionProvider` (design §8.1) — the leaf controls have
 * no other way to learn their canvas/decision and must never issue their
 * own query.
 */
export function useCanvasDecision(): CanvasDecisionValue {
  const v = useContext(CanvasDecisionContext)
  if (!v) throw new Error('shortcode rendered outside CanvasDecisionProvider')
  return v
}

/**
 * Non-throwing read of the canvas decision context (design §4.3 / Finding 1).
 * Returns `null` when rendered outside `CanvasDecisionProvider` instead of
 * throwing. Stateful DISPLAY shortcodes (`Collapsible`, `Tabs`) use this to
 * derive their remount-survival cache's `canvasName` segment without becoming
 * provider-bound: they are not trust-boundary controls, and many tests mount
 * them with no provider. The throwing `useCanvasDecision()` above remains the
 * trust-boundary read for `Choice`/`Approve`, which genuinely require a provider.
 */
export function useCanvasDecisionOptional(): CanvasDecisionValue | null {
  return useContext(CanvasDecisionContext)
}
