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
