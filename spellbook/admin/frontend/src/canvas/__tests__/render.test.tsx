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

describe('CanvasRender — element overrides (a, code, pre, table, th, td)', () => {
  // §2.1/§2.2: these six base-HTML elements are owned SOLELY by the override
  // map (Task 3 nulled the typography plugin's competing rules for exactly
  // these surfaces, so no specificity fight exists). Each override emits a
  // token-exact className set; the code/pre split uses the react-markdown 9.1.0
  // detection pinned in Task 6 (the dead v8 `inline` prop is gone — the block
  // predicate is /language-/.test(className), since the hast node carries no
  // parent key in 9.1.0). Each test asserts the COMPLETE className set with
  // { exact: true } (Level 5: fails on any dropped OR added token) plus the
  // exact rendered text, so a broken override class string or a mis-split
  // code branch cannot survive.

  it('renders [a] (link) with the override class set and exact href/text', () => {
    const { container } = render(
      <CanvasRender content={'[click here](https://example.com/page)'} />,
    )
    const anchor = container.querySelector('a')
    expect(anchor).not.toBeNull()
    // Complete intended class set for the `a` override (components.tsx).
    expect(anchor).toHaveClass(
      'text-accent-cyan hover:text-accent-green underline',
      { exact: true },
    )
    expect(anchor).toHaveAttribute('href', 'https://example.com/page')
    expect(anchor?.textContent).toBe('click here')
  })

  it('renders [inline code] as the styled span (not bare), exact class set', () => {
    // Inline code: className is UNDEFINED in 9.1.0 → /language-/ predicate is
    // false → the inline (styled) branch renders, NOT the bare block branch.
    const { container } = render(<CanvasRender content={'use `npm run`'} />)
    const code = container.querySelector('code')
    expect(code).not.toBeNull()
    // Complete intended class set for the inline `code` branch (components.tsx).
    expect(code).toHaveClass(
      'not-prose text-accent-cyan bg-bg-elevated px-1 py-0.5 rounded text-sm',
      { exact: true },
    )
    expect(code?.textContent).toBe('npm run')
    // It is NOT wrapped in a <pre> (inline, not a fenced block).
    expect(container.querySelector('pre')).toBeNull()
  })

  it('renders [fenced block] <pre> with override classes and a bare block <code>', () => {
    // Fenced block with a language: react-markdown 9.1.0 hands the inner
    // `code` override className="language-ts" → /language-/ predicate is true
    // → the BLOCK branch renders, which keeps the bare className (no styled
    // inline tokens) and lets the `pre` override own the container styling.
    const { container } = render(
      <CanvasRender content={'```ts\nconst x = 1\n```'} />,
    )
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    // Complete intended class set for the `pre` override (components.tsx).
    expect(pre).toHaveClass(
      'not-prose bg-bg-elevated border border-bg-border rounded p-3 overflow-x-auto text-sm',
      { exact: true },
    )
    const code = pre?.querySelector('code')
    expect(code).not.toBeNull()
    // Block branch: bare language className only — the inline styled tokens
    // (text-accent-cyan, px-1, …) must be ABSENT here. { exact: true } fails
    // if the inline branch leaked in.
    expect(code).toHaveClass('language-ts', { exact: true })
    expect(code?.textContent).toBe('const x = 1\n')
  })

  it('renders [table] <table>/<th>/<td> with the override class sets', () => {
    // remark-gfm parses the pipe table; the override map styles the table
    // family. Each element asserts its COMPLETE class set with { exact: true }.
    const { container } = render(
      <CanvasRender
        content={'| Col A | Col B |\n| --- | --- |\n| v1 | v2 |'}
      />,
    )
    const table = container.querySelector('table')
    expect(table).not.toBeNull()
    // Complete intended class set for the `table` override (components.tsx).
    expect(table).toHaveClass(
      'not-prose w-full border-collapse border border-bg-border my-3',
      { exact: true },
    )

    const headers = container.querySelectorAll('th')
    expect(Array.from(headers, (h) => h.textContent)).toEqual(['Col A', 'Col B'])
    headers.forEach((th) => {
      // Complete intended class set for the `th` override (components.tsx).
      expect(th).toHaveClass(
        'border border-bg-border bg-bg-elevated px-3 py-1.5 text-left font-mono text-xs uppercase tracking-widest text-text-secondary',
        { exact: true },
      )
    })

    const cells = container.querySelectorAll('td')
    expect(Array.from(cells, (c) => c.textContent)).toEqual(['v1', 'v2'])
    cells.forEach((td) => {
      // Complete intended class set for the `td` override (components.tsx).
      expect(td).toHaveClass(
        'border border-bg-border px-3 py-1.5 text-sm text-text-primary',
        { exact: true },
      )
    })
  })

  it('forwards GFM column alignment onto th and td (:-: → inline text-align style)', () => {
    // remark-gfm parses the `:-:` / default delimiter row into per-column
    // alignment; mdast-util-to-hast 13.x emits it as the hast `align` property
    // on the th/td nodes. react-markdown's JSX runtime
    // (hast-util-to-jsx-runtime, tableCellAlignToStyle defaults true) then
    // converts that `align` into an inline `style={{ textAlign }}` prop — NOT
    // an `align` prop. The override must forward rest props (which now carry
    // `style`) so the authored alignment survives; an inline text-align outranks
    // the recipe's text-left class in the cascade. Column A is centred (`:-:`);
    // column B is unaligned (`---`). Each element asserts its COMPLETE class set
    // with { exact: true } AND the exact inline style — both the presence of
    // text-align:center on the centred column and its ABSENCE on the unaligned
    // column (style attribute fully null), so a fix that drops the forwarded
    // style or leaks a style onto the wrong column fails.
    const { container } = render(
      <CanvasRender
        content={'| Col A | Col B |\n| :-: | --- |\n| v1 | v2 |'}
      />,
    )

    const headers = container.querySelectorAll('th')
    expect(Array.from(headers, (h) => h.textContent)).toEqual(['Col A', 'Col B'])
    // Centred header: full recipe class set is unchanged; the forwarded inline
    // style carries text-align: center (which beats the text-left class).
    expect(headers[0]).toHaveClass(
      'border border-bg-border bg-bg-elevated px-3 py-1.5 text-left font-mono text-xs uppercase tracking-widest text-text-secondary',
      { exact: true },
    )
    expect(headers[0].getAttribute('style')).toBe('text-align: center;')
    // Unaligned header: identical class set, and NO inline style is forwarded.
    expect(headers[1]).toHaveClass(
      'border border-bg-border bg-bg-elevated px-3 py-1.5 text-left font-mono text-xs uppercase tracking-widest text-text-secondary',
      { exact: true },
    )
    expect(headers[1].getAttribute('style')).toBe(null)

    const cells = container.querySelectorAll('td')
    expect(Array.from(cells, (c) => c.textContent)).toEqual(['v1', 'v2'])
    // Centred cell: full recipe class set is unchanged; the forwarded inline
    // style carries text-align: center.
    expect(cells[0]).toHaveClass(
      'border border-bg-border px-3 py-1.5 text-sm text-text-primary',
      { exact: true },
    )
    expect(cells[0].getAttribute('style')).toBe('text-align: center;')
    // Unaligned cell: identical class set, and NO inline style is forwarded.
    expect(cells[1]).toHaveClass(
      'border border-bg-border px-3 py-1.5 text-sm text-text-primary',
      { exact: true },
    )
    expect(cells[1].getAttribute('style')).toBe(null)
  })

  it('forwards a link title attribute through the [a] override (rest props)', () => {
    // `[text](url "tip")` carries a hast `title` property; react-markdown
    // spreads it as a `title` prop. The override must forward rest props so the
    // author-supplied title survives, alongside the exact override class set and
    // href. { exact: true } on the class set fails on any dropped OR added token.
    const { container } = render(
      <CanvasRender
        content={'[click here](https://example.com/page "tooltip text")'}
      />,
    )
    const anchor = container.querySelector('a')
    expect(anchor).not.toBeNull()
    expect(anchor).toHaveClass(
      'text-accent-cyan hover:text-accent-green underline',
      { exact: true },
    )
    expect(anchor).toHaveAttribute('href', 'https://example.com/page')
    expect(anchor).toHaveAttribute('title', 'tooltip text')
    expect(anchor?.textContent).toBe('click here')
  })
})

describe('CanvasRender — GFM task-list input → status icon override', () => {
  // §5 / DA-5: remark-gfm emits `<input type="checkbox" disabled checked?>`
  // for each `- [x]` / `- [ ]` task-list item. The `input` override
  // (components.tsx) replaces every CHECKBOX input with a display-only
  // status-icon span (no `<input>` in output): done → `☑`, pending → `☐`.
  // Non-checkbox inputs (e.g. an author-written `<input type="text">` passed
  // through by rehype-raw, or the Choice/Approve `type="radio"` controls)
  // fall through to a real `<input>` UNCHANGED. Each test asserts the
  // COMPLETE rendered structure (Level 5: exact outerHTML of every emitted
  // span, exact text, and the absence of any `<input>` for the checkbox case)
  // so a broken override — wrong icon glyph, missing data-checked, a leaked
  // `<input>`, or a swapped done/pending state — cannot survive.

  it('renders `- [x]` and `- [ ]` task-list checkboxes as status-icon spans (no <input>)', () => {
    // remark-gfm parses the two task-list items into <li> each containing an
    // <input type="checkbox" disabled> (checked for [x], unchecked for [ ]).
    // The override transforms BOTH into `task-icon` spans. The done item gets
    // data-checked="true" + ☑; the pending item gets data-checked="false" + ☐.
    // No <input> may remain anywhere in the output.
    const { container } = render(
      <CanvasRender content={'- [x] done\n- [ ] pending'} />,
    )

    const icons = container.querySelectorAll('[data-testid="task-icon"]')
    // Exactly two icons, in document order: done first, pending second.
    // Full outerHTML equality (Level 5): pins testid, data-checked, aria-hidden,
    // the glyph, AND that the element is a <span> with no extra attributes.
    expect(Array.from(icons, (el) => el.outerHTML)).toEqual([
      '<span data-testid="task-icon" data-checked="true" aria-hidden="true">☑</span>',
      '<span data-testid="task-icon" data-checked="false" aria-hidden="true">☐</span>',
    ])
    // The status icons are display-only: NO checkbox <input> survives the
    // override. A leaked disabled checkbox would fail this.
    expect(container.querySelector('input')).toBeNull()
  })

  it('passes a non-checkbox author-written <input> through to a real <input> unchanged', () => {
    // rehype-raw passes author-written raw HTML through; an `<input type="text">`
    // is NOT a task-list checkbox, so the override's else-branch must emit a real
    // `<input>` with its attributes intact. This pins that the override discriminates
    // on type === 'checkbox' and does not swallow every input. Full outerHTML
    // equality (Level 5): pins tag, type, value, AND the absence of any task-icon
    // span / data-checked attribute. A `placeholder` (uncontrolled) attribute
    // is used rather than `value` so the passthrough render stays free of
    // React's controlled-input-without-onChange warning — keeping the output
    // pristine while still exercising the non-checkbox else-branch.
    const { container } = render(
      <CanvasRender content={'<input type="text" placeholder="name">'} />,
    )
    const input = container.querySelector('input')
    expect(input).not.toBeNull()
    // Attribute order follows the DOM's serialization (alphabetical:
    // placeholder before type), not the source order.
    expect(input?.outerHTML).toBe('<input placeholder="name" type="text">')
    // The non-checkbox input must NOT have been transformed into a status icon.
    expect(container.querySelector('[data-testid="task-icon"]')).toBeNull()
  })
})

describe('CanvasRender — GATE-2 raw-string shortcode children re-parse', () => {
  // §4.6 GATE-2: content on the line IMMEDIATELY after an opening
  // children-content shortcode tag (no blank line) is swallowed by
  // CommonMark's raw-HTML-block rule. react-markdown + rehype-raw then
  // deliver the entire body as ONE plain string child — markdown left
  // UNPARSED. Without the renderer-side `renderChildren` fix, `**bold**`
  // appears as literal asterisks on screen. The fix detects raw-string-only
  // children and re-parses them through the same pipeline using the SHARED
  // components map, so the six element overrides (Task 10) apply to the
  // nested content too. The hazard is shared across Collapsible, Callout,
  // and Tabs; each gets its own pin. Healthy (blank-line / inline-element)
  // cases must pass through UNCHANGED — the fix only fires on raw-string
  // children.

  it('re-parses tight **bold** in a <collapsible> open body to a <strong> element', () => {
    // Body line sits immediately after the opening <collapsible open> tag,
    // with NO blank line → CommonMark raw-HTML-block hazard. Without the
    // fix the body is the literal string "**bold**"; with the fix it is a
    // re-parsed <strong>bold</strong>.
    const { container } = render(
      <CanvasRender content={'<collapsible open summary="More">\n**bold**\n</collapsible>'} />,
    )
    const body = screen.getByTestId('collapsible-body')
    const strong = body.querySelector('strong')
    expect(strong).not.toBeNull()
    expect(strong?.outerHTML).toBe('<strong>bold</strong>')
    // The literal markdown asterisks must NOT survive anywhere in the body.
    expect(body.textContent).toBe('bold')
    expect(container.innerHTML).not.toContain('**bold**')
  })

  it('re-parses tight `inline code` in a <collapsible> body through the shared code override', () => {
    // The nested re-parse pass uses the SAME components map, so the inline
    // `code` override (Task 10) styles the re-parsed inline code. This pins
    // that the re-parse routes through the shared map, not a bare pipeline.
    const { container } = render(
      <CanvasRender content={'<collapsible open summary="More">\nrun `npm run`\n</collapsible>'} />,
    )
    const body = screen.getByTestId('collapsible-body')
    const code = body.querySelector('code')
    expect(code).not.toBeNull()
    // Complete intended class set for the inline `code` override
    // (components.tsx) — proves the nested pass used the shared map.
    expect(code).toHaveClass(
      'not-prose text-accent-cyan bg-bg-elevated px-1 py-0.5 rounded text-sm',
      { exact: true },
    )
    expect(code?.textContent).toBe('npm run')
    expect(container.innerHTML).not.toContain('`npm run`')
  })

  it('re-parses tight **bold** in a <callout> body to a <strong> element', () => {
    // Same raw-HTML-block hazard inside the callout body div (Callout.tsx:46).
    render(
      <CanvasRender content={'<callout type="note" title="Heads up">\n**bold**\n</callout>'} />,
    )
    const callout = screen.getByTestId('callout')
    // The callout body is the second child div (first is the label row).
    const body = callout.querySelectorAll('div')[1]
    const strong = body.querySelector('strong')
    expect(strong).not.toBeNull()
    expect(strong?.outerHTML).toBe('<strong>bold</strong>')
    expect(body.textContent).toBe('bold')
  })

  it('re-parses tight **bold** in the active <tab> panel body to a <strong> element', async () => {
    // The hazard reaches the Tab body too; the active panel re-parses its
    // raw-string body (Tabs.tsx:74).
    const { container } = render(
      <CanvasRender
        content={'<tabs>\n<tab title="Alpha">\n**bold**\n</tab>\n</tabs>'}
      />,
    )
    await screen.findByTestId('tabs')
    const panel = container.querySelector('[role="tabpanel"]')
    expect(panel).not.toBeNull()
    const strong = panel?.querySelector('strong')
    expect(strong).not.toBeNull()
    expect(strong?.outerHTML).toBe('<strong>bold</strong>')
    expect(panel?.textContent).toBe('bold')
  })

  it('leaves healthy blank-line-separated <collapsible> body markdown unchanged (already elements)', () => {
    // A blank line after the opening tag lets CommonMark parse the body as a
    // real paragraph BEFORE it reaches the component, so children arrive as
    // ELEMENTS, not a raw string. renderChildren must pass these through
    // untouched — the body is a <p> wrapping a <strong>, exactly as upstream
    // produced it, with no double-wrapping from a spurious second parse.
    // The surrounding "\n" text nodes are CommonMark's whitespace around the
    // block-level paragraph; they are present upstream and must survive the
    // pass-through verbatim. Level 5: exact innerHTML of the body.
    const { container } = render(
      <CanvasRender content={'<collapsible open summary="More">\n\n**bold**\n\n</collapsible>'} />,
    )
    const body = screen.getByTestId('collapsible-body')
    expect(body.innerHTML).toBe('\n<p><strong>bold</strong></p>\n')
    // The literal markdown asterisks must NOT survive anywhere in the output.
    expect(container.innerHTML).not.toContain('**bold**')
  })

  it('passes MIXED (tight string + blank-line paragraph) children through verbatim — tight portion stays literal markdown', () => {
    // CHARACTERIZATION PIN (not RED-first): this behavior already exists; the
    // test pins it. §4.6's two-state model: renderChildren re-parses ONLY when
    // EVERY child is a raw string (isRawStringChildren's .every()). When the
    // author writes a tight line immediately after the opening tag AND a
    // separate blank-line-separated paragraph, CommonMark delivers a MIX: a
    // raw string sibling ("tight **a**") plus an already-parsed element sibling
    // (the <p><strong>b</strong></p> from the blank-line-separated portion).
    // .every() fails on the element sibling, so the array returns UNCHANGED and
    // the tight portion stays LITERAL markdown ("**a**" as text, not <strong>).
    // This is correct-by-design; the blank-line authoring discipline is the
    // author-side mitigation. Level 5: exact innerHTML of the body.
    render(
      <CanvasRender content={'<collapsible open summary="More">\ntight **a**\n\n**b**\n</collapsible>'} />,
    )
    const body = screen.getByTestId('collapsible-body')
    // Tight portion ("tight **a**") survives as literal markdown text; the
    // blank-line-separated "**b**" was parsed upstream into <p><strong>b</strong></p>.
    expect(body.innerHTML).toBe('\ntight **a**\n<p><strong>b</strong>\n</p>')
    // The literal asterisks of the TIGHT portion are present as text (the
    // passthrough left them unparsed); the blank-line portion was parsed.
    expect(body.textContent).toBe('\ntight **a**\nb\n')
  })
})
