import { useCanvasDecision } from '../CanvasDecisionContext'

interface ApproveProps {
  id?: string
  prompt?: string
  confirm_label?: string
  decline_label?: string
}

/**
 * Approval shortcode (§8.1/§8.2).
 *
 * ACTIVE iff a live decision in context matches this shortcode's `id` and
 * is still `pending`. Active → enabled confirm/decline buttons wired to
 * the hoisted `submit.mutate` from `useCanvasDecision()` (§8.1): confirm →
 * `value: "approved"`, decline → `value: "declined"`. Otherwise disabled.
 * Submission status/error is read from the hoisted context state (RT-6).
 *
 * Attribute parsing (`id`/`prompt`/`confirm_label`/`decline_label`) is
 * unchanged from the locked grammar.
 */
export function Approve({
  id,
  prompt,
  confirm_label,
  decline_label,
}: ApproveProps) {
  const { decision, submit, reauthenticate } = useCanvasDecision()

  const active =
    !!id && decision?.decision_id === id && decision?.status === 'pending'

  const errorCode = submit.status === 'error' ? submit.error?.code : undefined
  const terminalStatus =
    !!id && decision !== null && decision.decision_id === id
      ? decision.status
      : undefined

  // §8.2 state machine, highest-priority terminal states first. Terminal
  // branches return early below, so they win over the in-flight state by
  // ordering — `isSubmitting` is therefore derived from the submit status
  // alone (matching the page-level marker, RT-6), not coupled to `active`.
  const isAlreadyDecided = errorCode === 'already_decided'
  const isCancelled = errorCode === 'cancelled' || terminalStatus === 'cancelled'
  const isSubmitted =
    submit.status === 'success' ||
    terminalStatus === 'submitted' ||
    terminalStatus === 'consumed'
  const isSubmitting = submit.status === 'pending'
  const isValueError = errorCode === 'invalid_value'
  const isAuthError = errorCode === 'auth_expired'

  if (isAlreadyDecided) {
    return (
      <div
        data-testid="approve-already-decided"
        className="my-3 border border-bg-border p-3 opacity-70"
      >
        {prompt && (
          <p className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
            {prompt}
          </p>
        )}
        <p className="text-sm text-text-secondary">
          Already decided (another tab/click won)
        </p>
      </div>
    )
  }

  if (isCancelled) {
    return (
      <div
        data-testid="approve-cancelled"
        className="my-3 border border-bg-border p-3 opacity-70"
      >
        {prompt && (
          <p className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
            {prompt}
          </p>
        )}
        <p className="text-sm text-text-secondary">This decision was withdrawn</p>
      </div>
    )
  }

  if (isSubmitted) {
    return (
      <div
        data-testid="approve-submitted"
        className="my-3 border border-accent-green p-3"
      >
        {prompt && (
          <p className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
            {prompt}
          </p>
        )}
        <p className="text-sm text-accent-green">
          Submitted ✓ — agent is proceeding
        </p>
      </div>
    )
  }

  const buttonsDisabled = !active || isSubmitting

  return (
    <div
      aria-label={active ? prompt ?? 'approval' : 'approval (no live decision)'}
      data-testid="approve"
      className={
        active
          ? 'my-3 border border-bg-border p-3'
          : 'my-3 border border-bg-border p-3 opacity-70'
      }
    >
      {prompt && (
        <p className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
          {prompt}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={buttonsDisabled}
          data-testid={isSubmitting ? 'approve-submitting' : 'approve-confirm'}
          onClick={() => {
            if (id) submit.mutate({ decision_id: id, value: 'approved', free_text: null })
          }}
          className="px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest disabled:opacity-50"
        >
          {confirm_label ?? 'Approve'}
        </button>
        <button
          type="button"
          disabled={buttonsDisabled}
          data-testid="approve-decline"
          onClick={() => {
            if (id) submit.mutate({ decision_id: id, value: 'declined', free_text: null })
          }}
          className="px-3 py-1 border border-accent-red text-accent-red font-mono text-xs uppercase tracking-widest disabled:opacity-50"
        >
          {decline_label ?? 'Reject'}
        </button>
      </div>
      {isValueError && (
        <p className="mt-2 text-sm text-accent-red" data-testid="approve-value-error">
          {submit.error?.message ?? 'Invalid selection'}
        </p>
      )}
      {isAuthError && (
        <>
          <p className="mt-2 text-sm text-accent-amber" data-testid="approve-auth-error">
            Your admin session expired. Your submission was NOT lost; the decision
            is still open.
          </p>
          <button
            type="button"
            data-testid="approve-reauth"
            onClick={() => reauthenticate()}
            className="mt-2 px-3 py-1 border border-accent-amber text-accent-amber font-mono text-xs uppercase tracking-widest"
          >
            Reauthenticate
          </button>
        </>
      )}
    </div>
  )
}
