import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

// Mock the lazy-loaded heavy chunks so the test environment does not have
// to evaluate `mermaid` or `react-vega` — both bring DOM-dependent setup
// that is irrelevant to dispatch-pipeline testing.
vi.mock('../shortcodes/MermaidImpl', () => ({
  default: () => <div data-testid="mermaid-impl" />,
}))
vi.mock('../shortcodes/ChartImpl', () => ({
  default: () => <div data-testid="chart-impl" />,
}))

// Import AFTER the mocks above so `Diagram` / `Chart` pick up the mocked
// dynamic imports.
import { CanvasRender } from '../render'
import { Choice } from '../shortcodes/Choice'
import { Approve } from '../shortcodes/Approve'
import { CanvasDecisionContext } from '../CanvasDecisionContext'
import type { CanvasDecisionValue } from '../CanvasDecisionContext'
import type { ReactNode } from 'react'

// In production `CanvasRender` is always wrapped in `CanvasDecisionProvider`
// (CanvasDetail, §8.1). The activated <choice>/<approve> shortcodes call
// `useCanvasDecision()`, which throws outside a provider, so the dispatch
// tests for those two render inside a no-live-decision provider (decision:
// null → controls render disabled).
const noDecisionValue: CanvasDecisionValue = {
  canvasName: 'plan-x',
  decision: null,
  submit: { mutate: () => {}, status: 'idle', error: null, lastFreeText: null },
  reauthenticate: () => {},
}
function withProvider(ui: ReactNode) {
  return (
    <CanvasDecisionContext.Provider value={noDecisionValue}>
      {ui}
    </CanvasDecisionContext.Provider>
  )
}

describe('CanvasRender — shortcode dispatch pipeline', () => {
  it('renders plain markdown headings via remark-gfm', () => {
    render(<CanvasRender content="# Hello" />)
    expect(
      screen.getByRole('heading', { level: 1, name: 'Hello' }),
    ).toBeInTheDocument()
  })

  it('renders h2 via the plugin baseline with no override class (probe removed)', () => {
    // The prototype `h2` override added `class="mt-8"` as a typography
    // specificity probe. With it removed, h2 flows through the
    // @tailwindcss/typography plugin baseline and the override map
    // contributes no className. A classless heading renders as bare
    // `<h2>Heading</h2>` (verified: h1, which has no override, emits
    // `<h1>Hello</h1>` with no class attribute). Level 5: exact outerHTML.
    const { container } = render(<CanvasRender content="## Heading" />)
    const h2 = container.querySelector('h2')
    expect(h2?.outerHTML).toBe('<h2>Heading</h2>')
    // The class attribute is fully absent, not just missing the probe token.
    expect(h2?.getAttribute('class')).toBe(null)
  })

  it('dispatches <callout> to the Callout component', () => {
    render(
      <CanvasRender
        content={'<callout type="warning" title="Heads up">Body text</callout>'}
      />,
    )
    const callout = screen.getByTestId('callout')
    expect(callout).toBeInTheDocument()
    expect(callout).toHaveAttribute('data-callout-type', 'warning')
    expect(screen.getByText('Body text')).toBeInTheDocument()
  })

  it('renders a warning callout with the accent-amber token (not undefined accent-yellow)', () => {
    render(
      <CanvasRender
        content={'<callout type="warning" title="Heads up">Body text</callout>'}
      />,
    )
    const callout = screen.getByTestId('callout')
    // The warning <aside> border resolves to the defined accent-amber token.
    // Exact class set (Level 5): every token the warning aside must carry.
    expect(callout).toHaveClass(
      'my-3',
      'border-l-4',
      'border-accent-amber',
      'bg-bg-elevated',
      'px-3',
      'py-2',
    )
    expect(callout).not.toHaveClass('border-accent-yellow')
    // The label row uses the same token.
    const label = callout.querySelector('div')
    expect(label).toHaveClass(
      'font-mono',
      'text-xs',
      'uppercase',
      'tracking-widest',
      'mb-1',
      'text-accent-amber',
    )
    expect(label).not.toHaveClass('text-accent-yellow')
  })

  it('dispatches <tabs> + <tab> with active panel rendered', async () => {
    render(
      <CanvasRender
        content={
          '<tabs>\n<tab title="Alpha">aaa</tab>\n<tab title="Beta">bbb</tab>\n</tabs>'
        }
      />,
    )
    expect(await screen.findByTestId('tabs')).toBeInTheDocument()
    // First tab is active by default; its body renders.
    expect(screen.getByText('aaa')).toBeInTheDocument()
    // Tab bar contains both titles.
    expect(screen.getByRole('tab', { name: 'Alpha' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Beta' })).toBeInTheDocument()
  })

  it('exposes <tab> children when rendered standalone (named export)', () => {
    // Standalone <tab> with no parent <tabs> still renders content, which
    // is what react-markdown does when it finds a <tab> tag at the top
    // level. Covers the named `Tab` export.
    render(<CanvasRender content={'<tab title="solo">just-content</tab>'} />)
    expect(screen.getByTestId('tab')).toBeInTheDocument()
    expect(screen.getByText('just-content')).toBeInTheDocument()
  })

  it('dispatches <choice> to the activated control (disabled with no live decision)', () => {
    const content =
      '<choice id="c1" prompt="Pick one" options=\'[{"value":"a","label":"Alpha"},{"value":"b","label":"Beta"}]\'></choice>'
    render(withProvider(<CanvasRender content={content} />))
    expect(screen.getByTestId('choice')).toBeInTheDocument()
    expect(screen.getByText('Pick one')).toBeInTheDocument()
    // No live decision matches id → control is disabled.
    expect(screen.getByLabelText('Alpha')).toBeDisabled()
  })

  it('dispatches <approve> to the activated control (disabled with no live decision)', () => {
    const content =
      '<approve id="a1" prompt="Ship it?" confirm_label="Yes" decline_label="No"></approve>'
    render(withProvider(<CanvasRender content={content} />))
    expect(screen.getByTestId('approve')).toBeInTheDocument()
    expect(screen.getByText('Ship it?')).toBeInTheDocument()
    // No live decision matches id → confirm/decline buttons are disabled.
    expect(screen.getByText('Yes')).toBeDisabled()
    expect(screen.getByText('No')).toBeDisabled()
  })

  it('dispatches <diagram> to the lazy MermaidImpl', async () => {
    const content = '<diagram caption="flow">flowchart LR\nA --> B</diagram>'
    render(<CanvasRender content={content} />)
    expect(await screen.findByTestId('diagram')).toBeInTheDocument()
    // Lazy chunk resolved (mocked).
    expect(await screen.findByTestId('mermaid-impl')).toBeInTheDocument()
    expect(screen.getByText('flow')).toBeInTheDocument()
  })

  it('dispatches <chart> to the lazy ChartImpl with parsed spec', async () => {
    const spec = '{"mark":"bar","encoding":{"x":{"field":"a"}}}'
    const content = `<chart caption="metrics">${spec}</chart>`
    render(<CanvasRender content={content} />)
    expect(await screen.findByTestId('chart')).toBeInTheDocument()
    expect(await screen.findByTestId('chart-impl')).toBeInTheDocument()
    expect(screen.getByText('metrics')).toBeInTheDocument()
  })
})

describe('CanvasRender — not-prose boundaries on shortcode content regions', () => {
  // §2.4: every shortcode region that re-parses markdown must carry
  // `not-prose` so the @tailwindcss/typography cascade (margins, line-height)
  // does not leak into the re-parsed body and double-space it. Each test
  // asserts the COMPLETE className set with { exact: true } — a Level 5
  // assertion that fails both on a missing `not-prose` token AND on any
  // dropped/added sibling token.

  it('renders the <tabs> active panel with not-prose severing the prose cascade', async () => {
    const { container } = render(
      <CanvasRender
        content={
          '<tabs>\n<tab title="Alpha">aaa</tab>\n<tab title="Beta">bbb</tab>\n</tabs>'
        }
      />,
    )
    await screen.findByTestId('tabs')
    const panel = container.querySelector('[role="tabpanel"]')
    expect(panel).not.toBeNull()
    // Complete intended class set for the active tab panel (Tabs.tsx:73).
    expect(panel).toHaveClass('not-prose p-3 text-sm text-text-primary', {
      exact: true,
    })
  })

  it('renders the <collapsible> open body with not-prose severing the prose cascade', () => {
    render(
      <CanvasRender content={'<collapsible open summary="More">body text</collapsible>'} />,
    )
    const body = screen.getByTestId('collapsible-body')
    // Complete intended class set for the collapsible body (Collapsible.tsx:45-48).
    expect(body).toHaveClass('not-prose px-3 py-2 text-sm text-text-primary', {
      exact: true,
    })
  })

  it('renders the <chart> figure wrapper with not-prose (defensive)', async () => {
    const spec = '{"mark":"bar","encoding":{"x":{"field":"a"}}}'
    render(<CanvasRender content={`<chart caption="metrics">${spec}</chart>`} />)
    const chart = await screen.findByTestId('chart')
    // Complete intended class set for the chart figure wrapper (Chart.tsx:65).
    expect(chart).toHaveClass('not-prose my-3', { exact: true })
  })

  it('renders the <diagram> figure wrapper with not-prose (defensive)', async () => {
    render(<CanvasRender content={'<diagram caption="flow">flowchart LR\nA --> B</diagram>'} />)
    const diagram = await screen.findByTestId('diagram')
    // Complete intended class set for the diagram figure wrapper (Diagram.tsx:35).
    expect(diagram).toHaveClass('not-prose my-3', { exact: true })
  })

  it('PIN: <callout> body keeps not-prose severing the prose cascade', () => {
    render(
      <CanvasRender content={'<callout type="note" title="Heads up">Body text</callout>'} />,
    )
    const callout = screen.getByTestId('callout')
    // The callout body is the second child div (the first is the label row).
    // Callout.tsx:46 — this is a KEEP-pin; not-prose already rides on it.
    const body = callout.querySelectorAll('div')[1]
    expect(body).toHaveClass('not-prose text-sm text-text-primary', {
      exact: true,
    })
  })
})

describe('Choice — not-prose on every render-root branch', () => {
  // §2.4 / F1: Choice has FOUR distinct render roots (three terminal early
  // returns + the live fieldset). Each must carry `not-prose` as its first
  // token so a post-decision `canvas_write` never lets the prose cascade leak
  // into terminal-state status text. Each test drives ONE branch via context
  // state and asserts the COMPLETE className set with { exact: true } — a
  // Level 5 assertion that fails on a missing `not-prose` token AND on any
  // dropped/added sibling token. The frozen §6.1 testids pin which branch.

  // Each branch builds on this provider value; per-test overrides set the
  // exact state that selects the target branch (Choice.tsx §8.2 ordering).
  const baseValue: CanvasDecisionValue = {
    canvasName: 'plan-x',
    decision: null,
    submit: { mutate: () => {}, status: 'idle', error: null, lastFreeText: null },
    reauthenticate: () => {},
  }
  const choiceUi = (
    <Choice id="d1" prompt="Pick" options='[{"value":"a","label":"A"}]' />
  )
  function renderWith(value: CanvasDecisionValue) {
    return render(
      <CanvasDecisionContext.Provider value={value}>
        {choiceUi}
      </CanvasDecisionContext.Provider>,
    )
  }

  it('already-decided root carries not-prose (errorCode=already_decided)', () => {
    renderWith({
      ...baseValue,
      submit: {
        ...baseValue.submit,
        status: 'error',
        error: Object.assign(new Error('x'), { code: 'already_decided' }),
      },
    })
    const root = screen.getByTestId('choice-already-decided')
    // Choice.tsx:78-82 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3 opacity-70', {
      exact: true,
    })
  })

  it('cancelled root carries not-prose (decision.status=cancelled)', () => {
    renderWith({
      ...baseValue,
      decision: {
        decision_id: 'd1',
        kind: 'choice',
        prompt: 'Pick',
        options: [{ value: 'a', label: 'A' }],
        status: 'cancelled',
      },
    })
    const root = screen.getByTestId('choice-cancelled')
    // Choice.tsx:96-100 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3 opacity-70', {
      exact: true,
    })
  })

  it('submitted root carries not-prose (submit.status=success)', () => {
    renderWith({
      ...baseValue,
      submit: { ...baseValue.submit, status: 'success' },
    })
    const root = screen.getByTestId('choice-submitted')
    // Choice.tsx:112-116 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-accent-green p-3', {
      exact: true,
    })
  })

  it('live (active) fieldset root carries not-prose (matching pending decision)', () => {
    renderWith({
      ...baseValue,
      decision: {
        decision_id: 'd1',
        kind: 'choice',
        prompt: 'Pick',
        options: [{ value: 'a', label: 'A' }],
        status: 'pending',
      },
    })
    const root = screen.getByTestId('choice')
    // Choice.tsx:131-141 — active ternary arm; not-prose prepended to the
    // frozen class set (the active arm omits opacity-70).
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3', {
      exact: true,
    })
  })

  it('live (inactive) fieldset root carries not-prose (no matching live decision)', () => {
    // No matching pending decision → the inactive ternary arm renders
    // (opacity-70). Pins not-prose on the OTHER arm of the live conditional,
    // so a fix that only patches the active arm fails here.
    renderWith(baseValue)
    const root = screen.getByTestId('choice')
    // Choice.tsx:137-140 — inactive ternary arm; not-prose prepended.
    expect(root).toHaveClass(
      'not-prose my-3 border border-bg-border p-3 opacity-70',
      { exact: true },
    )
  })
})

describe('Approve — not-prose on every render-root branch', () => {
  // §2.4 / F1: Approve has FOUR distinct render roots (three terminal early
  // returns + the live container whose className is itself a ternary, so it
  // contributes TWO branches: active and inactive). Each must carry
  // `not-prose` as its first token so a post-decision `canvas_write` never
  // lets the prose cascade leak into terminal-state status text. Each test
  // drives ONE branch via context state and asserts the COMPLETE className
  // set with { exact: true } — a Level 5 assertion that fails on a missing
  // `not-prose` token AND on any dropped/added sibling token. The frozen
  // §6.1 testids pin which branch. Mirrors the Choice block (Task 8).

  // Each branch builds on this provider value; per-test overrides set the
  // exact state that selects the target branch (Approve.tsx §8.2 ordering).
  const baseValue: CanvasDecisionValue = {
    canvasName: 'plan-x',
    decision: null,
    submit: { mutate: () => {}, status: 'idle', error: null, lastFreeText: null },
    reauthenticate: () => {},
  }
  const approveUi = (
    <Approve id="a1" prompt="Ship it?" confirm_label="Yes" decline_label="No" />
  )
  function renderWith(value: CanvasDecisionValue) {
    return render(
      <CanvasDecisionContext.Provider value={value}>
        {approveUi}
      </CanvasDecisionContext.Provider>,
    )
  }

  it('already-decided root carries not-prose (errorCode=already_decided)', () => {
    renderWith({
      ...baseValue,
      submit: {
        ...baseValue.submit,
        status: 'error',
        error: Object.assign(new Error('x'), { code: 'already_decided' }),
      },
    })
    const root = screen.getByTestId('approve-already-decided')
    // Approve.tsx:54-58 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3 opacity-70', {
      exact: true,
    })
  })

  it('cancelled root carries not-prose (decision.status=cancelled)', () => {
    renderWith({
      ...baseValue,
      decision: {
        decision_id: 'a1',
        kind: 'approve',
        prompt: 'Ship it?',
        options: null,
        status: 'cancelled',
      },
    })
    const root = screen.getByTestId('approve-cancelled')
    // Approve.tsx:72-76 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3 opacity-70', {
      exact: true,
    })
  })

  it('submitted root carries not-prose (submit.status=success)', () => {
    renderWith({
      ...baseValue,
      submit: { ...baseValue.submit, status: 'success' },
    })
    const root = screen.getByTestId('approve-submitted')
    // Approve.tsx:88-92 — not-prose prepended to the frozen class set.
    expect(root).toHaveClass('not-prose my-3 border border-accent-green p-3', {
      exact: true,
    })
  })

  it('live (active) container root carries not-prose (matching pending decision)', () => {
    renderWith({
      ...baseValue,
      decision: {
        decision_id: 'a1',
        kind: 'approve',
        prompt: 'Ship it?',
        options: null,
        status: 'pending',
      },
    })
    const root = screen.getByTestId('approve')
    // Approve.tsx:107-115 — active ternary arm; not-prose prepended to the
    // frozen class set (the active arm omits opacity-70).
    expect(root).toHaveClass('not-prose my-3 border border-bg-border p-3', {
      exact: true,
    })
  })

  it('live (inactive) container root carries not-prose (no matching live decision)', () => {
    // No matching pending decision → the inactive ternary arm renders
    // (opacity-70). Pins not-prose on the OTHER arm of the live conditional,
    // so a fix that only patches the active arm fails here.
    renderWith(baseValue)
    const root = screen.getByTestId('approve')
    // Approve.tsx:107-115 — inactive ternary arm; not-prose prepended.
    expect(root).toHaveClass(
      'not-prose my-3 border border-bg-border p-3 opacity-70',
      { exact: true },
    )
  })
})
