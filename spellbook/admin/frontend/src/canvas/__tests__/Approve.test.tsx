import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CanvasDecisionContext } from '../CanvasDecisionContext'
import type { CanvasDecisionValue } from '../CanvasDecisionContext'
import { Approve } from '../shortcodes/Approve'
import type { ReactNode } from 'react'

const baseSubmit = { mutate: vi.fn(), status: 'idle' as const, error: null, lastFreeText: null }
// Existing tests construct the context value without `reauthenticate`; inject
// a default no-op so they keep typechecking while the new D1 tests pass an
// explicit spy.
function wrap(
  value: Omit<CanvasDecisionValue, 'reauthenticate'> & { reauthenticate?: () => void },
  ui: ReactNode,
) {
  const full: CanvasDecisionValue = { reauthenticate: () => {}, ...value }
  return render(<CanvasDecisionContext.Provider value={full}>{ui}</CanvasDecisionContext.Provider>)
}

describe('Approve activation', () => {
  it('approve button calls mutate with approved', () => {
    const mutate = vi.fn()
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'pending' },
        submit: { ...baseSubmit, mutate },
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Ship' }))
    expect(mutate).toHaveBeenCalledWith({ decision_id: 'd1', value: 'approved', free_text: null })
  })

  it('decline button calls mutate with declined', () => {
    const mutate = vi.fn()
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'pending' },
        submit: { ...baseSubmit, mutate },
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Hold' }))
    expect(mutate).toHaveBeenCalledWith({ decision_id: 'd1', value: 'declined', free_text: null })
  })

  it('disabled when no matching decision', () => {
    wrap(
      { canvasName: 'plan-x', decision: null, submit: baseSubmit },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    expect((screen.getByRole('button', { name: 'Ship' }) as HTMLButtonElement).disabled).toBe(true)
  })

  // M1: the confirm button carries an Approve-distinct testid while in
  // flight (approve-submitting), NOT the page-level "decision-submitting"
  // marker, so the two are independently selectable.
  it('confirm button is data-testid="approve-submitting" while in flight', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'pending' },
        submit: { ...baseSubmit, status: 'pending' },
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    const button = screen.getByTestId('approve-submitting')
    expect(button.tagName).toBe('BUTTON')
    expect(button.textContent).toBe('Ship')
    expect((button as HTMLButtonElement).disabled).toBe(true)
    // The page-level marker id is NOT used by the leaf button.
    expect(screen.queryByTestId('decision-submitting')).toBeNull()
  })

  // M2: a submit that is still 'pending' while the decision has flipped to a
  // terminal status (here 'cancelled', as a concurrent WS update would
  // deliver) must render the terminal panel — the interactive controls must
  // NOT re-appear/re-enable mid-POST. Terminal branches win by ordering.
  it('renders terminal panel (not live controls) when decision flips terminal mid-POST', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'cancelled' },
        submit: { ...baseSubmit, status: 'pending' },
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    expect(screen.getByTestId('approve-cancelled').textContent).toContain(
      'This decision was withdrawn',
    )
    // No interactive control of any kind survives the terminal flip.
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByTestId('approve-submitting')).toBeNull()
    expect(screen.queryByTestId('approve-confirm')).toBeNull()
    expect(screen.queryByTestId('approve-decline')).toBeNull()
  })

  // M2: isSubmitting is derived from submit.status === 'pending' alone, NOT
  // coupled to `active`. When a POST is in flight but `active` has gone false
  // for a NON-terminal reason (the decision projection momentarily drops to
  // null on a refetch), the confirm control must still show its in-flight
  // testid — it must NOT revert to the idle approve-confirm affordance.
  it('keeps the in-flight affordance when active is false but submit is pending (decision null)', () => {
    wrap(
      { canvasName: 'plan-x', decision: null, submit: { ...baseSubmit, status: 'pending' } },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    const button = screen.getByTestId('approve-submitting')
    expect(button.textContent).toBe('Ship')
    expect((button as HTMLButtonElement).disabled).toBe(true)
    // The idle approve-confirm affordance must NOT be present mid-POST.
    expect(screen.queryByTestId('approve-confirm')).toBeNull()
  })

  // Coverage gap (§8.4 / D1): an auth_expired error surfaces the re-auth
  // banner with TRUTHFUL copy (no "Re-authenticating…" auto-bounce claim) and
  // an explicit Reauthenticate action, while keeping the decision open
  // (controls still rendered, not a terminal panel).
  it('renders the auth-expired re-auth banner with the truthful copy on error.code="auth_expired"', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'pending' },
        submit: {
          ...baseSubmit,
          status: 'error',
          error: Object.assign(new Error('Admin session expired'), { code: 'auth_expired' }),
        },
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    expect(screen.getByTestId('approve-auth-error').textContent).toBe(
      'Your admin session expired. Your submission was NOT lost; the decision is still open.',
    )
    // The old auto-bounce copy is GONE — it falsely claimed an automatic
    // re-authentication that never happened.
    expect(screen.queryByText(/Re-authenticating/i)).toBeNull()
    // Decision stays open: the live control is still present, not a terminal panel.
    expect(screen.getByTestId('approve')).toBeInTheDocument()
    expect(screen.queryByTestId('approve-submitted')).toBeNull()
    expect(screen.queryByTestId('approve-cancelled')).toBeNull()
  })

  // D1: the auth-expired panel exposes an explicit Reauthenticate button that
  // invokes the hoisted `reauthenticate` handler exactly once (which drives the
  // reload-through-login flow). The control must NOT auto-bounce.
  it('fires the hoisted reauthenticate handler exactly once when Reauthenticate is clicked', () => {
    const reauthenticate = vi.fn()
    wrap(
      {
        canvasName: 'plan-x',
        decision: { decision_id: 'd1', kind: 'approve', prompt: 'Ship?', options: null, status: 'pending' },
        submit: {
          ...baseSubmit,
          status: 'error',
          error: Object.assign(new Error('Admin session expired'), { code: 'auth_expired' }),
        },
        reauthenticate,
      },
      <Approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold" />,
    )
    const button = screen.getByTestId('approve-reauth')
    expect(button.tagName).toBe('BUTTON')
    expect(button.textContent).toBe('Reauthenticate')
    expect(reauthenticate).toHaveBeenCalledTimes(0)
    fireEvent.click(button)
    expect(reauthenticate).toHaveBeenCalledTimes(1)
    expect(reauthenticate).toHaveBeenCalledWith()
  })
})
