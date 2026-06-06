import { useState } from 'react'
import { useCanvasDecision } from '../CanvasDecisionContext'

interface ChoiceOption {
  value: string
  label: string
}

interface ChoiceProps {
  id?: string
  prompt?: string
  // `react-markdown` delivers HTML attributes as strings; we parse JSON
  // out of `options` on render.
  options?: string
}

function parseOptions(raw: string | undefined): ChoiceOption[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (o): o is ChoiceOption =>
        !!o &&
        typeof o === 'object' &&
        typeof (o as ChoiceOption).value === 'string' &&
        typeof (o as ChoiceOption).label === 'string',
    )
  } catch {
    return []
  }
}

/**
 * Single-choice radio shortcode (§8.1/§8.2).
 *
 * The control is ACTIVE iff a live decision in context matches this
 * shortcode's `id` and is still `pending`. Active → enabled radio group +
 * Submit, wired to the hoisted `submit.mutate` from `useCanvasDecision()`
 * (§8.1). Otherwise it renders disabled. Submission status/error is read
 * from the hoisted context state (RT-6); only the ephemeral radio
 * selection is local.
 *
 * Attribute parsing (`id`/`prompt`/`options` as strings) is unchanged from
 * the locked children/attribute-hybrid grammar
 * (docs/spellbook-canvas-shortcode-spike/GRAMMAR-LOCK.md; canvas MVP design §9.2).
 */
export function Choice({ id, prompt, options }: ChoiceProps) {
  const opts = parseOptions(options)
  const name = id ?? 'choice'
  const { decision, submit, reauthenticate } = useCanvasDecision()
  const [selected, setSelected] = useState<string | null>(null)

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
        data-testid="choice-already-decided"
        className="not-prose my-3 border border-bg-border p-3 opacity-70"
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
        data-testid="choice-cancelled"
        className="not-prose my-3 border border-bg-border p-3 opacity-70"
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
        data-testid="choice-submitted"
        className="not-prose my-3 border border-accent-green p-3"
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

  const submitDisabled = !active || isSubmitting || selected === null

  return (
    <fieldset
      disabled={!active || isSubmitting}
      aria-label={active ? prompt ?? 'choice' : 'choice (no live decision)'}
      data-testid="choice"
      className={
        active
          ? 'not-prose my-3 border border-bg-border p-3'
          : 'not-prose my-3 border border-bg-border p-3 opacity-70'
      }
    >
      {prompt && (
        <legend className="px-2 font-mono text-xs uppercase tracking-widest text-text-secondary">
          {prompt}
        </legend>
      )}
      <ul role="radiogroup" className="space-y-1 mt-1">
        {opts.map((opt, i) => (
          <li key={`${opt.value}-${i}`}>
            <label className="flex items-center gap-2 text-sm text-text-primary">
              <input
                type="radio"
                name={name}
                value={opt.value}
                disabled={!active || isSubmitting}
                checked={selected === opt.value}
                onChange={() => setSelected(opt.value)}
              />
              {opt.label}
            </label>
          </li>
        ))}
      </ul>
      {isValueError && (
        <p className="mt-2 text-sm text-accent-red" data-testid="choice-value-error">
          {submit.error?.message ?? 'Invalid selection'}
        </p>
      )}
      {isAuthError && (
        <>
          <p className="mt-2 text-sm text-accent-amber" data-testid="choice-auth-error">
            Your admin session expired. Your submission was NOT lost; the decision
            is still open.
          </p>
          <button
            type="button"
            data-testid="choice-reauth"
            onClick={() => reauthenticate()}
            className="mt-2 px-3 py-1 border border-accent-amber text-accent-amber font-mono text-xs uppercase tracking-widest"
          >
            Reauthenticate
          </button>
        </>
      )}
      <button
        type="button"
        disabled={submitDisabled}
        data-testid={isSubmitting ? 'choice-submitting' : 'choice-submit'}
        onClick={() => {
          if (id && selected !== null) {
            submit.mutate({ decision_id: id, value: selected, free_text: null })
          }
        }}
        className="mt-2 px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest disabled:opacity-50"
      >
        {isSubmitting ? 'Submitting…' : 'Submit'}
      </button>
    </fieldset>
  )
}
