import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CanvasDecisionContext } from '../CanvasDecisionContext'
import type { CanvasDecisionValue } from '../CanvasDecisionContext'
import { Choice } from '../shortcodes/Choice'
import type { ReactNode } from 'react'

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
const baseSubmit = { mutate: vi.fn(), status: 'idle' as const, error: null, lastFreeText: null }

describe('Choice activation', () => {
  it('renders active radio group when matching pending decision', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [
            { value: 'a', label: 'A' },
            { value: 'b', label: 'B' },
          ],
          status: 'pending',
        },
        submit: baseSubmit,
      },
      <Choice
        id="d1"
        prompt="Pick"
        options='[{"value":"a","label":"A"},{"value":"b","label":"B"}]'
      />,
    )
    // Assert each radio individually by its rendered label, and that the
    // label↔value wiring matches the two options exactly. `every(...).toBe(false)`
    // only proves "not all disabled" — it would pass if one radio were disabled,
    // mislabeled, or if an extra/missing option rendered. Pin both.
    const radioA = screen.getByLabelText('A') as HTMLInputElement
    const radioB = screen.getByLabelText('B') as HTMLInputElement
    expect(radioA.disabled).toBe(false)
    expect(radioB.disabled).toBe(false)
    expect(radioA.value).toBe('a')
    expect(radioB.value).toBe('b')
    // Exactly two radios — no extra/missing options.
    expect(screen.getAllByRole('radio')).toHaveLength(2)
  })

  it('renders disabled when no live decision matches id', () => {
    wrap(
      { canvasName: 'plan-x', decision: null, submit: baseSubmit },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    expect((screen.getByRole('radio') as HTMLInputElement).disabled).toBe(true)
  })

  it('submit calls mutate with selected value', () => {
    const mutate = vi.fn()
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [
            { value: 'a', label: 'A' },
            { value: 'b', label: 'B' },
          ],
          status: 'pending',
        },
        submit: { ...baseSubmit, mutate },
      },
      <Choice
        id="d1"
        prompt="Pick"
        options='[{"value":"a","label":"A"},{"value":"b","label":"B"}]'
      />,
    )
    fireEvent.click(screen.getByLabelText('B'))
    fireEvent.click(screen.getByRole('button', { name: /submit/i }))
    expect(mutate).toHaveBeenCalledWith({ decision_id: 'd1', value: 'b', free_text: null })
  })

  it('shows already_decided read-only on 409', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [{ value: 'a', label: 'A' }],
          status: 'pending',
        },
        submit: {
          ...baseSubmit,
          status: 'error',
          error: Object.assign(new Error('x'), { code: 'already_decided' }),
        },
      },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    expect(screen.getByText(/already decided/i)).toBeInTheDocument()
  })

  // M1: the leaf submit button carries a Choice-distinct testid while in
  // flight (choice-submitting), NOT the page-level "decision-submitting"
  // marker, so the two are independently selectable.
  it('submit button is data-testid="choice-submitting" while in flight', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [{ value: 'a', label: 'A' }],
          status: 'pending',
        },
        submit: { ...baseSubmit, status: 'pending' },
      },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    const button = screen.getByTestId('choice-submitting')
    expect(button.tagName).toBe('BUTTON')
    expect(button.textContent).toBe('Submitting…')
    expect((button as HTMLButtonElement).disabled).toBe(true)
    // The page-level marker id is NOT used by the leaf button.
    expect(screen.queryByTestId('decision-submitting')).toBeNull()
  })

  // M2: a submit that is still 'pending' while the decision has flipped to a
  // terminal status (here 'cancelled', as a concurrent WS update would
  // deliver) must render the terminal panel — the interactive control must
  // NOT re-appear/re-enable mid-POST. Terminal branches win by ordering.
  it('renders terminal panel (not a live control) when decision flips terminal mid-POST', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [{ value: 'a', label: 'A' }],
          status: 'cancelled',
        },
        submit: { ...baseSubmit, status: 'pending' },
      },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    expect(screen.getByTestId('choice-cancelled').textContent).toContain(
      'This decision was withdrawn',
    )
    // No interactive control of any kind survives the terminal flip.
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('radio')).toBeNull()
    expect(screen.queryByTestId('choice-submitting')).toBeNull()
    expect(screen.queryByTestId('choice-submit')).toBeNull()
  })

  // M2: isSubmitting is derived from submit.status === 'pending' alone, NOT
  // coupled to `active`. When a POST is in flight but `active` has gone false
  // for a NON-terminal reason (the decision projection momentarily drops to
  // null on a refetch), the control must still show its in-flight state —
  // it must NOT visually re-enable to the idle "Submit" affordance mid-POST.
  it('keeps the in-flight affordance when active is false but submit is pending (decision null)', () => {
    wrap(
      { canvasName: 'plan-x', decision: null, submit: { ...baseSubmit, status: 'pending' } },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    const button = screen.getByTestId('choice-submitting')
    expect(button.textContent).toBe('Submitting…')
    expect((button as HTMLButtonElement).disabled).toBe(true)
    // The idle "Submit" affordance must NOT be present mid-POST.
    expect(screen.queryByTestId('choice-submit')).toBeNull()
  })

  // Coverage gap (§8.4 / D1): an auth_expired error surfaces the re-auth
  // banner with TRUTHFUL copy (no "Re-authenticating…" auto-bounce claim) and
  // an explicit Reauthenticate action, while keeping the decision open (control
  // still rendered, not a terminal panel).
  it('renders the auth-expired re-auth banner with the truthful copy on error.code="auth_expired"', () => {
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [{ value: 'a', label: 'A' }],
          status: 'pending',
        },
        submit: {
          ...baseSubmit,
          status: 'error',
          error: Object.assign(new Error('Admin session expired'), {
            code: 'auth_expired',
          }),
        },
      },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    expect(screen.getByTestId('choice-auth-error').textContent).toBe(
      'Your admin session expired. Your submission was NOT lost; the decision is still open.',
    )
    // The old auto-bounce copy is GONE — it falsely claimed an automatic
    // re-authentication that never happened.
    expect(screen.queryByText(/Re-authenticating/i)).toBeNull()
    // Decision stays open: the live control is still present, not a terminal panel.
    expect(screen.getByTestId('choice')).toBeInTheDocument()
    expect(screen.queryByTestId('choice-submitted')).toBeNull()
    expect(screen.queryByTestId('choice-cancelled')).toBeNull()
  })

  // D1: the auth-expired panel exposes an explicit Reauthenticate button that
  // invokes the hoisted `reauthenticate` handler exactly once (which drives the
  // reload-through-login flow). The control must NOT auto-bounce.
  it('fires the hoisted reauthenticate handler exactly once when Reauthenticate is clicked', () => {
    const reauthenticate = vi.fn()
    wrap(
      {
        canvasName: 'plan-x',
        decision: {
          decision_id: 'd1',
          kind: 'choice',
          prompt: 'Pick',
          options: [{ value: 'a', label: 'A' }],
          status: 'pending',
        },
        submit: {
          ...baseSubmit,
          status: 'error',
          error: Object.assign(new Error('Admin session expired'), {
            code: 'auth_expired',
          }),
        },
        reauthenticate,
      },
      <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />,
    )
    const button = screen.getByTestId('choice-reauth')
    expect(button.tagName).toBe('BUTTON')
    expect(button.textContent).toBe('Reauthenticate')
    expect(reauthenticate).toHaveBeenCalledTimes(0)
    fireEvent.click(button)
    expect(reauthenticate).toHaveBeenCalledTimes(1)
    expect(reauthenticate).toHaveBeenCalledWith()
  })
})
