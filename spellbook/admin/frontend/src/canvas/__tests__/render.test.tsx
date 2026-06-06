import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

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
import {
  collapsibleOpenState,
  tabsActiveState,
  evictCanvasShortcodeState,
  __resetCanvasShortcodeState,
} from '../shortcodes/shortcodeState'

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
    const tab = screen.getByTestId('tab')
    expect(tab).toBeInTheDocument()
    expect(screen.getByText('just-content')).toBeInTheDocument()
    // §2.4 belt: the standalone-Tab fallback root carries not-prose so the
    // prose cascade does not leak into its raw body. Complete class set
    // (Level 5: { exact: true } fails on a missing not-prose OR any added token).
    expect(tab).toHaveClass('not-prose', { exact: true })
  })

  it('renders an empty <tabs> fallback root with not-prose (no <tab> children)', () => {
    // A <tabs> with no <tab> children hits the empty-Tabs fallback (Tabs.tsx),
    // which renders the raw body so the agent still sees it. §2.4 belt: that
    // fallback root must carry not-prose too. Complete class set (Level 5:
    // { exact: true }).
    render(<CanvasRender content={'<tabs>loose body</tabs>'} />)
    const empty = screen.getByTestId('tabs-empty')
    expect(empty).toBeInTheDocument()
    expect(empty).toHaveTextContent('loose body')
    expect(empty).toHaveClass('not-prose', { exact: true })
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

  it('RT-7b: a block shortcode on its own line inside a not-prose body — the injected <p>-wrap lands INSIDE the not-prose boundary', () => {
    // §8.2 RT-7b / §4.1: a block-level shortcode (here a nested <callout>)
    // sitting on its OWN line, blank-line-separated, inside a <collapsible open>
    // body is parsed upstream as a real block. react-markdown then wraps that
    // block in a paragraph — the known cosmetic `<p>`-wrap artifact. The design
    // contract is that this `<p>` is PROSE-IMMUNE because it lands INSIDE the
    // body's `not-prose` region (the region is the `<p>`'s ANCESTOR), so the
    // typography plugin's `.prose p` margin rule is severed and never reaches
    // it. This pins WHICH SIDE of the boundary the artifact lands on: a
    // regression that put `not-prose` on a sibling (not the wrapping region)
    // would leave the injected `<p>` outside the boundary and reintroduce prose
    // margins.
    render(
      <CanvasRender
        content={
          '<collapsible open summary="More">\n\n<callout type="note" title="Inner">inner body</callout>\n\n</collapsible>'
        }
      />,
    )
    const body = screen.getByTestId('collapsible-body')
    // The body region carries not-prose (the boundary).
    expect(body).toHaveClass('not-prose px-3 py-2 text-sm text-text-primary', {
      exact: true,
    })
    // The injected <p>-wrap is a DIRECT child of the not-prose body region, and
    // it wraps the nested callout <aside>. Asserting the parent chain pins that
    // the <p> is a descendant of the not-prose region (region is its ancestor),
    // which is the whole RT-7b guarantee.
    const wrappedP = body.querySelector(':scope > p')
    expect(wrappedP).not.toBeNull()
    // The <p> directly contains the nested callout (the block shortcode), and
    // the closest not-prose ancestor of that <p> is the collapsible body — so
    // the prose cascade is severed above the artifact.
    const nestedCallout = wrappedP?.querySelector('[data-testid="callout"]')
    expect(nestedCallout).not.toBeNull()
    expect(nestedCallout?.getAttribute('data-callout-type')).toBe('note')
    // The nearest ancestor carrying not-prose IS the collapsible body region
    // (not some element below the <p>): closest('.not-prose') from the <p>
    // resolves to the body, proving the boundary is the <p>'s ancestor.
    expect(wrappedP?.closest('.not-prose')).toBe(body)
  })

  it('gives the <collapsible> open body region an accessible name (button labels the region)', () => {
    // a11y: the disclosure button labels the region it controls, so the region
    // is not an unnamed landmark. The button's `aria-controls` points at the
    // region id and the region's `aria-labelledby` points back at the button id
    // (ids are useId-generated, so assert the round-trip rather than literals).
    // The region is also reachable by its accessible name via getByRole.
    render(
      <CanvasRender content={'<collapsible open summary="More">body text</collapsible>'} />,
    )
    const button = screen.getByRole('button')
    const region = screen.getByTestId('collapsible-body')
    const buttonId = button.getAttribute('id')
    const regionId = region.getAttribute('id')
    // Both ids are present, non-empty, and distinct.
    expect(typeof buttonId).toBe('string')
    expect(buttonId).not.toBe('')
    expect(typeof regionId).toBe('string')
    expect(regionId).not.toBe('')
    expect(buttonId).not.toBe(regionId)
    // The control/label relationship round-trips exactly.
    expect(button.getAttribute('aria-controls')).toBe(regionId)
    expect(region.getAttribute('aria-labelledby')).toBe(buttonId)
    // The region is exposed with the button's text ("More") as its
    // accessible name — proves the labelledby wiring is honored by ARIA.
    expect(
      screen.getByRole('region', { name: 'More' }),
    ).toBe(region)
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

  it('prose scope: CanvasRender emits NO prose token — the `prose` wrapper is the parent (CanvasDetail) responsibility only', () => {
    // §8.2 prose-scope `[structural]` (focused form): the `prose prose-invert`
    // class lives ONLY on the canvas-content wrapper that CanvasDetail.tsx:122
    // renders AROUND <CanvasRender>; PageLayout/title/banner sit OUTSIDE that
    // wrapper and never carry it. CanvasDetail is owned by a sibling cluster
    // (pages/CanvasDetail.tsx + its test), so this render.test.tsx pin asserts
    // the boundary from the CanvasRender side: the rendered shortcode/markdown
    // output itself emits ZERO `prose` tokens. The wrapper being the SOLE
    // prose-bearing element — and PageLayout/title/banner excluded — is the
    // structural complement, verified at the CanvasDetail level (eyeball/
    // structural note) since this file does not mount PageLayout.
    //
    // Content deliberately exercises markdown blocks (heading, paragraph, list)
    // AND a shortcode region, so a regression that injected `prose`/`prose-invert`
    // anywhere in CanvasRender's own output (e.g. a stray wrapper added inside a
    // shortcode) is caught. A bare-substring scan would pass on `prose-invert`
    // appearing in a comment; here we scan the live DOM classList of every
    // emitted element, so only a real rendered class token can trip it.
    const { container } = render(
      <CanvasRender
        content={
          '# Title\n\nIntro paragraph.\n\n- one\n- two\n\n<callout type="note" title="Note">callout body</callout>'
        }
      />,
    )
    // Collect every class token across the whole rendered subtree.
    const allTokens = Array.from(container.querySelectorAll('*')).flatMap((el) =>
      Array.from(el.classList),
    )
    // CanvasRender's output carries NEITHER `prose` NOR `prose-invert` — only
    // the parent wrapper does. (It DOES carry `not-prose` tokens on shortcode
    // regions; those are distinct and expected — assert they are present so this
    // test cannot pass on an empty render.)
    expect(allTokens.filter((t) => t === 'prose')).toEqual([])
    expect(allTokens.filter((t) => t === 'prose-invert')).toEqual([])
    expect(allTokens).toContain('not-prose')
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
    // Choice.tsx:78-82 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4 opacity-70', {
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
    // Choice.tsx:96-100 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4 opacity-70', {
      exact: true,
    })
  })

  it('submitted root carries not-prose (submit.status=success)', () => {
    renderWith({
      ...baseValue,
      submit: { ...baseValue.submit, status: 'success' },
    })
    const root = screen.getByTestId('choice-submitted')
    // Choice.tsx:112-116 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-accent-green p-4', {
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
    // pinned class set (the active arm omits opacity-70).
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4', {
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
      'not-prose my-3 rounded border border-bg-border p-4 opacity-70',
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
    // Approve.tsx:54-58 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4 opacity-70', {
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
    // Approve.tsx:72-76 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4 opacity-70', {
      exact: true,
    })
  })

  it('submitted root carries not-prose (submit.status=success)', () => {
    renderWith({
      ...baseValue,
      submit: { ...baseValue.submit, status: 'success' },
    })
    const root = screen.getByTestId('approve-submitted')
    // Approve.tsx:88-92 — not-prose prepended to the pinned class set.
    expect(root).toHaveClass('not-prose my-3 rounded border border-accent-green p-4', {
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
    // pinned class set (the active arm omits opacity-70).
    expect(root).toHaveClass('not-prose my-3 rounded border border-bg-border p-4', {
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
      'not-prose my-3 rounded border border-bg-border p-4 opacity-70',
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
    // Attribute order follows the element attribute-list (insertion) order
    // produced by React/jsdom — here that happens to be placeholder before
    // type — not the markdown source order.
    expect(input?.outerHTML).toBe('<input placeholder="name" type="text">')
    // The non-checkbox input must NOT have been transformed into a status icon.
    expect(container.querySelector('[data-testid="task-icon"]')).toBeNull()
  })

  it('transforms a TIGHT task list inside a <collapsible> body through the nested re-parse (no <input>)', () => {
    // Canonical plan-approval composition: a task list nested inside a
    // collapsible. The two task-list lines sit IMMEDIATELY after the opening
    // <collapsible open> tag (no blank line) → CommonMark's raw-HTML-block rule
    // swallows them as ONE raw string child. renderChildren (§4.6 GATE-2) then
    // re-parses that string through the SHARED components map, so the SAME
    // `input` override that iconifies top-level task lists must fire on the
    // re-parsed checkboxes too. This pins that the icon transform survives the
    // nested re-parse: a regression that re-parsed the nested body through a
    // bare pipeline (without the shared map) would leak raw disabled <input>
    // checkboxes instead. Asserts the COMPLETE rendered structure (Level 5:
    // exact outerHTML of both emitted spans, done first / pending second, and
    // the absence of any <input> anywhere) — identical to the top-level
    // task-list pin, now proven to hold one parse-pass deeper.
    const { container } = render(
      <CanvasRender
        content={'<collapsible open summary="Tasks">\n- [x] done\n- [ ] pending\n</collapsible>'}
      />,
    )
    const body = screen.getByTestId('collapsible-body')
    const icons = body.querySelectorAll('[data-testid="task-icon"]')
    // Exactly two icons, in document order: done first, pending second. Full
    // outerHTML equality pins testid, data-checked, aria-hidden, the glyph, AND
    // that each element is a bare <span> — the same shape the top-level pass
    // produces, now emitted by the nested re-parse.
    expect(Array.from(icons, (el) => el.outerHTML)).toEqual([
      '<span data-testid="task-icon" data-checked="true" aria-hidden="true">☑</span>',
      '<span data-testid="task-icon" data-checked="false" aria-hidden="true">☐</span>',
    ])
    // No disabled checkbox <input> may survive the nested re-parse: a bare
    // (non-shared-map) re-parse pipeline would leak one here.
    expect(container.querySelector('input')).toBeNull()
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

describe('Step-0 spike — node.position availability under the production pipeline', () => {
  // Task 13 Step 0 (Finding 2): the remount-survival cache key's trailing
  // segment is `${node?.position?.start?.offset ?? 0}`. That key is only stable
  // (distinct same-summary instances → distinct keys) if react-markdown@9 +
  // remark-gfm@4 + rehype-raw@7 populate `node.position.start.offset` for a
  // custom shortcode component (rehype-raw re-parses raw HTML and CAN drop
  // positions in some configs). This spike pins the empirical reality so the
  // offset-key branch does not regress silently. It renders TWO same-tag
  // shortcodes through the EXACT production plugin stack (the same plugins
  // render.tsx wires) and captures each instance's node.position via a probe
  // component registered under the `collapsible` tag, asserting the COMPLETE
  // recorded position set with exact equality (Level 5).

  it('pins: a <collapsible> shortcode receives a populated node.position.start.offset', () => {
    const records: Array<{
      summary: string | undefined
      offset: number | undefined
      offsetIsNumber: boolean
    }> = []

    // Two collapsibles, byte-distinct opening tags in the source. The probe
    // records each instance's source offset. The opening `<collapsible ...>`
    // tags begin at known byte positions in `md` below.
    const md =
      '<collapsible summary="First">a</collapsible>\n\n' +
      '<collapsible summary="Second">b</collapsible>'

    renderToStaticMarkupViaRender(md, records)

    // The source offsets are fully determined by the markdown string above:
    //   "<collapsible summary=\"First\">a</collapsible>\n\n" is 46 chars
    //   ("<collapsible summary=\"First\">" = 29, "a" = 1, "</collapsible>" = 14,
    //    "\n\n" = 2  →  29+1+14+2 = 46), so the SECOND opening tag starts at 46.
    // GOLD (Level 5): full equality on the COMPLETE recorded set. A pipeline
    // that dropped positions (offset undefined) or collapsed both to the same
    // offset would fail this exact-equality assertion.
    expect(records).toEqual([
      { summary: 'First', offset: 0, offsetIsNumber: true },
      { summary: 'Second', offset: 46, offsetIsNumber: true },
    ])
  })

  // Helper kept inside the describe so the probe component is local to the spike.
  function renderToStaticMarkupViaRender(
    md: string,
    records: Array<{
      summary: string | undefined
      offset: number | undefined
      offsetIsNumber: boolean
    }>,
  ): void {
    interface ProbeProps {
      summary?: string
      node?: { position?: { start?: { offset?: number } } }
    }
    const probe = ({ summary, node }: ProbeProps) => {
      const offset = node?.position?.start?.offset
      records.push({
        summary,
        offset,
        offsetIsNumber: typeof offset === 'number',
      })
      return null
    }
    render(
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{ collapsible: probe } as never}
      >
        {md}
      </ReactMarkdown>,
    )
  }
})

describe('shortcodeState — cache module (reset + per-canvas eviction)', () => {
  // Pure-logic pins for the module-scoped caches. These exercise the cache
  // primitives directly (no React), so a regression in key-prefix matching or
  // an incomplete clear is caught independent of the component wiring.

  beforeEach(__resetCanvasShortcodeState)

  it('__resetCanvasShortcodeState clears BOTH maps completely', () => {
    collapsibleOpenState.set('plan-x::A::0', true)
    collapsibleOpenState.set('plan-y::B::5', false)
    tabsActiveState.set('plan-x::T1|T2::0', 2)
    tabsActiveState.set('plan-y::T3|T4::9', 1)

    __resetCanvasShortcodeState()

    // Full-equality on the emptied maps (Level 5): a partial clear that left
    // any entry behind fails here.
    expect(Array.from(collapsibleOpenState.entries())).toEqual([])
    expect(Array.from(tabsActiveState.entries())).toEqual([])
  })

  it('evictCanvasShortcodeState removes ONLY the named canvas, leaving others intact', () => {
    collapsibleOpenState.set('plan-x::A::0', true)
    collapsibleOpenState.set('plan-x::B::12', false)
    collapsibleOpenState.set('plan-y::A::0', true)
    tabsActiveState.set('plan-x::T1|T2::0', 2)
    tabsActiveState.set('plan-y::T3|T4::0', 1)

    evictCanvasShortcodeState('plan-x')

    // Only plan-y survivors remain, with their exact cached values. Full
    // entry-set equality (Level 5): an over-eager sweep that dropped plan-y, or
    // a prefix bug that missed a plan-x key, fails here.
    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['plan-y::A::0', true],
    ])
    expect(Array.from(tabsActiveState.entries())).toEqual([
      ['plan-y::T3|T4::0', 1],
    ])
  })

  it('evictCanvasShortcodeState matches on the full `name::` prefix, not a bare substring', () => {
    // `plan-x` must NOT evict `plan-x2`'s entries: the prefix is `plan-x::`,
    // and `plan-x2::A::0` does not start with `plan-x::`. Pins that eviction is
    // delimiter-anchored, so a canvas whose name is a prefix of another's is
    // not collateral damage.
    collapsibleOpenState.set('plan-x::A::0', true)
    collapsibleOpenState.set('plan-x2::A::0', true)
    tabsActiveState.set('plan-x::T::0', 3)
    tabsActiveState.set('plan-x2::T::0', 4)

    evictCanvasShortcodeState('plan-x')

    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['plan-x2::A::0', true],
    ])
    expect(Array.from(tabsActiveState.entries())).toEqual([
      ['plan-x2::T::0', 4],
    ])
  })
})

describe('CanvasRender — remount-survival state cache (Collapsible + Tabs)', () => {
  // Task 13 (design §4.3): every `canvas_write` remounts the shortcode leaves,
  // so local `useState` resets. The module-scoped caches keyed by stable
  // identity (canvas + summary/titles + source offset) restore open/active
  // state on remount. These tests toggle state, unmount, remount with the SAME
  // source/canvas, and assert the state survived. The Step-0 spike confirmed
  // `node.position.start.offset` is populated, so distinct same-summary
  // instances carry distinct keys (the multi-instance independence test pins
  // that branch). All renders here are provider-less (canvasName segment = '')
  // — the non-throwing `useCanvasDecisionOptional()` read keeps them working.

  beforeEach(__resetCanvasShortcodeState)

  it('Collapsible open state survives unmount + remount (default-closed → toggled open)', () => {
    const content = '<collapsible summary="More">body text</collapsible>'

    const first = render(<CanvasRender content={content} />)
    // Default closed: no open attr → starts closed.
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'false',
    )
    // Operator opens it.
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'true',
    )
    // The cache now holds the open state under the stable key (provider-less →
    // canvasName ''; summary 'More'; single instance at source offset 0).
    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['::More::0', true],
    ])

    // canvas_write → remount: unmount, then mount the SAME content fresh.
    first.unmount()
    render(<CanvasRender content={content} />)

    // Without the cache the fresh mount would default closed; with it, the
    // open state is restored.
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'true',
    )
    expect(screen.getByTestId('collapsible-body')).toHaveTextContent('body text')
  })

  it('Collapsible toggled-closed state survives remount (open attr → toggled shut)', () => {
    // The inverse: an `open`-attr collapsible toggled SHUT must stay shut after
    // remount. Pins that the cache value (false) wins over the `open` initial,
    // so a fix that only restores the true case fails here.
    const content = '<collapsible open summary="More">body text</collapsible>'

    const first = render(<CanvasRender content={content} />)
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'true',
    )
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'false',
    )
    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['::More::0', false],
    ])

    first.unmount()
    render(<CanvasRender content={content} />)

    // Restored CLOSED despite the `open` attribute: cache value wins.
    expect(screen.getByTestId('collapsible')).toHaveAttribute(
      'data-collapsible-open',
      'false',
    )
    expect(screen.queryByTestId('collapsible-body')).toBeNull()
  })

  it('Tabs active-tab selection survives unmount + remount (tab 2 stays active)', async () => {
    const content =
      '<tabs>\n<tab title="Alpha">aaa</tab>\n<tab title="Beta">bbb</tab>\n</tabs>'

    const first = render(<CanvasRender content={content} />)
    await screen.findByTestId('tabs')
    // First tab active by default → its body renders.
    expect(screen.getByText('aaa')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    // Select tab 2 (Beta).
    fireEvent.click(screen.getByRole('tab', { name: 'Beta' }))
    expect(screen.getByText('bbb')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    // Cache holds active index 1 under the stable key (provider-less → ''
    // canvas; joined titles 'Alpha|Beta'; single instance at source offset 0).
    expect(Array.from(tabsActiveState.entries())).toEqual([
      ['::Alpha|Beta::0', 1],
    ])

    // Remount with the same content.
    first.unmount()
    render(<CanvasRender content={content} />)
    await screen.findByTestId('tabs')

    // Tab 2 stays active across the remount (fixes the pre-existing Tabs
    // snap-shut bug).
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByText('bbb')).toBeInTheDocument()
  })

  it('two same-summary collapsibles get DISTINCT keys → independent open state (offsets available)', () => {
    // Multi-instance documentation pin (§4.3) for the POSITIONS-AVAILABLE branch
    // the Step-0 spike selected. Two collapsibles both summarized "Details"
    // carry DISTINCT node.position.start.offset values → distinct cache keys →
    // independent state. Opening the FIRST must NOT open the SECOND. The first
    // opening `<collapsible summary="Details">` tag starts at source offset 0;
    // "<collapsible summary=\"Details\">a</collapsible>\n\n" is 48 chars, so the
    // second starts at offset 48.
    const content =
      '<collapsible summary="Details">a</collapsible>\n\n' +
      '<collapsible summary="Details">b</collapsible>'

    render(<CanvasRender content={content} />)
    const collapsibles = screen.getAllByTestId('collapsible')
    expect(collapsibles).toHaveLength(2)
    // Both default closed.
    expect(collapsibles[0]).toHaveAttribute('data-collapsible-open', 'false')
    expect(collapsibles[1]).toHaveAttribute('data-collapsible-open', 'false')

    // Open the FIRST only.
    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0])

    // First open, second STILL closed: distinct keys → independent state.
    expect(collapsibles[0]).toHaveAttribute('data-collapsible-open', 'true')
    expect(collapsibles[1]).toHaveAttribute('data-collapsible-open', 'false')
    // The cache holds exactly the first instance's key, at offset 0, value true
    // — the second instance (offset 48) is untouched. Full entry-set equality
    // (Level 5) pins both the distinct offsets and the independence.
    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['::Details::0', true],
    ])
  })

  it('DOCUMENTS the duplicate-default-summary swapped-order limit: state follows occurrence-index, not instance (§4.3 accepted limitation)', () => {
    // §8.2 / F2 / RT-2: the remount-survival guarantee is SINGLE-INSTANCE
    // (a uniquely- or authored-summary collapsible survives a remount). The
    // accepted limitation (§4.3) is that TWO collapsibles BOTH defaulting to
    // the same summary ("Details") key on `canvasName::summary::sourceOffset`
    // — and when the SAME source positions render DIFFERENT bodies (a reorder),
    // the cached open-state follows the OFFSET (occurrence-index), not the
    // instance content. This test pins that limitation as KNOWN rather than
    // letting a future change silently "fix" or worsen it.
    //
    // Both collapsibles omit `summary`, so both default to "Details". The first
    // opening `<collapsible>` tag starts at source offset 0; the second after
    // the "\n\n" separator. Body "a" is at offset 0, body "b" second.
    const contentAB =
      '<collapsible>a</collapsible>\n\n<collapsible>b</collapsible>'
    const first = render(<CanvasRender content={contentAB} />)

    // Open the FIRST collapsible (body "a", at source offset 0).
    fireEvent.click(screen.getAllByRole('button')[0])
    // The cache holds exactly one entry, keyed by the offset-0 position with
    // the default "Details" summary — NOT by the body content. Full entry-set
    // equality (Level 5) pins that the key is occurrence-index-anchored.
    expect(Array.from(collapsibleOpenState.entries())).toEqual([
      ['::Details::0', true],
    ])

    // Remount with the bodies SWAPPED: "b" now occupies source offset 0, "a"
    // occupies the second position. Same default summaries, same byte offsets.
    first.unmount()
    const contentBA =
      '<collapsible>b</collapsible>\n\n<collapsible>a</collapsible>'
    render(<CanvasRender content={contentBA} />)

    const collapsibles = screen.getAllByTestId('collapsible')
    expect(collapsibles).toHaveLength(2)
    // The OPEN state followed the OFFSET (position 0), not the instance: the
    // first-position collapsible is open and the second is closed — exactly the
    // pre-swap open/closed shape, now applied to swapped content. A fix that
    // tracked instance identity instead would invert this (second open).
    expect(
      collapsibles.map((c) => c.getAttribute('data-collapsible-open')),
    ).toEqual(['true', 'false'])
    // The single rendered body is the one now at offset 0 — body "b", the
    // SWAPPED-IN content — proving the cached open-state stuck to the position,
    // not to body "a" that was originally opened. This exact text is the crux
    // of the accepted limitation: a position-anchored cache shows "b" here; an
    // instance-anchored cache would show "a".
    const openBodies = screen.queryAllByTestId('collapsible-body')
    expect(openBodies.map((b) => b.textContent)).toEqual(['b'])
  })
})

// The operator's ACTUAL offending decision page (`lfq-phase15-batch2`, §8.2):
// the content-rich page whose styling collapse motivated this whole feature.
// Embedded VERBATIM (rather than read from ~/.local/spellbook at test time) so
// the pin is hermetic and deterministic — the structural contract is fixed to
// THIS content, not to a mutable on-disk file. It exercises, in one render:
// a context callout (note), two GFM tables, three <tabs> blocks (one per
// operator question) each with four <tab> options, and tip/note callouts
// NESTED inside the active tab panels — exactly the "callouts, GFM tables,
// tabbed options with nested callouts" composition §8.2 names.
const LFQ_FIXTURE = `# Phase 1.5 — Batch 2

Three remaining operator questions for the \`elijahr/lockfree\` v0.1.0 design. Reply in the terminal with your picks (free-text caveats welcome).

<callout type="note" title="Context recap">
**Locked already (Phase 0 + Batch 1):** v0.1.0 fresh start, no tag carry-over, lockfreequeues frozen until rename, \`lockfree/smr/debra_plus\` namespace, explicit imports only, generic \`Queue[ManagedRef[X], ...]\` API shape, ManagedSlice IN scope, PR bot = gemini-code-assist + axiomantic-momus parallel.

**Open:** CI matrix, Nimony cell mode + scope, Iterator/async tier 2.
</callout>

---

## Q4. CI matrix scope

How much should the CI matrix cover at v0.1.0?

**Current source-repo matrices:**

| Repo | OS rows | Nim | Sanitizers |
|---|---|---|---|
| lockfreequeues | ubuntu-latest, ubuntu-24.04-arm, macos-latest | stable | TSan + ASan |
| nim-debra | ubuntu-latest, ubuntu-24.04-arm | stable | TSan + ASan |

Union dedup'd is approximately 24 base cells across MM lanes (orc, c++ orc, arc, refc, atomicArc-TSAN, ASAN).

<tabs>
<tab title="A. Union + extras (Recommended)">

**Comprehensive matrix.**

- Base: union of both source repos' OS × MM × backend cells (about 24-28).
- Add: Valgrind cell (Linux x86_64, single MM lane).
- Add: Helgrind cell (Linux x86_64, single MM lane).
- Add: Nim devel cell (catches upstream API drift; the \`=copy\`/\`=destroy\`/\`nimIncRef\` family symbols ManagedRef shims against).
- Add: Nimony cell (continue-on-error per Q5).

Total: roughly 28-32 cells. Wall-clock impact: moderate.

<callout type="tip" title="Why Valgrind plus Helgrind">
Neither source repo currently has these. Valgrind catches use-after-free in the ManagedRef destructor walk; Helgrind catches happens-before violations the C11 sanitizers miss. For a library positioning itself on lock-free correctness, both pay off.
</callout>

</tab>
<tab title="B. Trim to core">

Fastest CI; lose breadth.

- ubuntu-latest + macos-latest, all MM lanes.
- Drop: ubuntu-24.04-arm, nimony, Valgrind, Helgrind, Nim-devel.

Risk: missing bugs that only surface under arm64 atomics (LSE vs LL/SC differences on RPi-class hardware), under leak detectors, or under upstream Nim API drift.

</tab>
<tab title="C. Union but defer leak detectors">

Get the comprehensive build matrix; postpone Valgrind + Helgrind to v0.2.

- All cells from option A except Valgrind + Helgrind.
- Cost: misses a category of bugs in the v0.1.0 ship.

</tab>
<tab title="D. Custom">

Operator-specified custom matrix. I'll write a draft markdown table; you redline it before CI work starts.

</tab>
</tabs>

---

## Q5. Nimony cell mode + scope expectations

Nimony is Araq's next-gen Nim compiler. Per handoff research Q2/Q4: 387 stars, pre-release, daily commits, timeline slipping past autumn-2025 target. Two language modes: **compat** (Nim 2 compatible, less actively developed) and **aufbruch** (clean break, atomic-arc MM, where the active work is).

<tabs>
<tab title="A. continue-on-error + aufbruch + partial port OK (Recommended)">

**Best-effort posture, documented gap.**

- CI cell mode: \`continue-on-error: true\` (nimony regression doesn't block PR-dance).
- Target mode: \`aufbruch\` (where active dev is; \`compat\` is the slower-moving fallback).
- Acceptable v0.1.0 scope if ManagedRef/ManagedSlice prove non-portable: ship atomics + smr + queues compile-and-pass on nimony, ManagedRef + ManagedSlice marked Nim-2.x-only.

<callout type="note" title="Why this is likely right">
nimony's MM model (atomic-arc only, no cycle collector yet) means the user-side \`ref\` story is semantically safer but doesn't change the queue-as-MM-bypasser problem. ManagedRef still needed under nimony, but the compat shim is genuinely simpler (no orc cyclic variants). Trade-off: cycles through queued refs will LEAK until nimony's cycle collector ships. Document prominently in the nimony section of \`docs/guide/memory-management.md\`.
</callout>

</tab>
<tab title="B. Hard-gate nimony">

Highest bar. Risks nimony itself breaking PRs unrelated to nimony work. Not recommended given nimony's instability.

</tab>
<tab title="C. Defer nimony to v0.2">

Drop nimony from v0.1.0. Cleaner v0.1.0 release; loses future-proofing signal.

Cost: when nimony stabilizes (Araq targets within about a year), having NO port story means lockfree is invisible to nimony adopters until v0.2 lands.

</tab>
<tab title="D. continue-on-error + compat mode">

Bets on \`compat\` rather than \`aufbruch\`. \`compat\` is the "try to be Nim 2 compatible" path; porting easier short-term but gets fewer commits than \`aufbruch\`. Likely the wrong horse.

</tab>
</tabs>

---

## Q6. Iterator + async integration scope

The handoff defines three tiers with very different cost profiles:

| Tier | What | Cost | RT-safe? |
|---|---|---|---|
| **Tier 1** Sync iterators | items/pairs/drain over pop() until empty | ~30 LOC per queue | yes |
| **Tier 2** Notify primitive | Waitable handle (eventfd/kqueue/WaitOnAddress); push signals "one available" | substantial cross-platform | no (push not RT) |
| **Tier 3** Async adapters | chronos / asyncdispatch / passive (nimony); multi-queue select | per-adapter design surface | depends |

<tabs>
<tab title="A. Tier 1 + Tier 2 Linux-only eventfd (Recommended)">

**Real integration story without full cross-platform polish.**

- Tier 1: in (sync iterators, trivial).
- Tier 2: Linux-only eventfd, marked **experimental**, API frozen for v0.2 cross-platform expansion (kqueue + WaitOnAddress).
- Tier 3: deferred to v0.2+.

<callout type="tip" title="Why Linux-only is honest">
The eventfd API shape is small enough to design fully (one-shot vs edge-triggered, fd lifecycle, fork safety). The cross-platform abstraction question — what's the right unified Nim API across eventfd / kqueue EVFILT_USER / WaitOnAddress / io_uring — needs real-use data first. Shipping Linux-only marked experimental gathers that data without painting yourself into a v0.1.0 corner.
</callout>

</tab>
<tab title="B. Tier 1 only — defer notify primitives">

Smallest surface. Users wanting async wait on v0.2.

Cleanest v0.1.0 scope; loses the "real integration story" signal. Users have to roll their own notification primitive on top of the queue, which is doable (busy-poll + sleep, Nim threadpool channels) but not what a v0.1.0 "first-class lock-free umbrella" should make people do.

</tab>
<tab title="C. Tier 1 + Tier 2 cross-platform">

Full eventfd + kqueue + WaitOnAddress in v0.1.0. Biggest surface; risks slipping v0.1.0.

Pays off if you want a polished story at first ship. Risk: cross-platform notify primitive design is famously bikesheddable (semaphore semantics, edge vs level, fork safety, fd inheritance), and "we'll figure out the unified API as we ship" often means "we shipped the wrong API and now we're stuck."

</tab>
<tab title="D. Tier 1 + Tier 2 Linux + Tier 3 chronos">

Notify primitive + the one async framework adapter most likely needed (chronos is Nim 2's de-facto async; nimbus, status, nim-libp2p all use it).

Adds the chronos adapter design surface but skips asyncdispatch/passive. Reasonable if you have specific chronos users in mind. Watch for: chronos \`Future[T]\` integration needs \`await\` semantics + cancellation, and the q-empty + cancel race is non-trivial.

</tab>
</tabs>

---

## Reply format

Type your picks back in the terminal in any format that makes the choices unambiguous:

- \`A, A, A\` (one per question in order Q4/Q5/Q6)
- \`Q4=A, Q5=A, Q6=A\`
- Free-text with caveats: \`Q4 A but only if Valgrind doesn't blow CI time; Q5 A; Q6 A but mark eventfd experimental loudly\`

Free-text caveats flow into the design doc as constraints.
`

describe('CanvasRender — full lfq decision-page fixture (§8.2 integration pin)', () => {
  // §8.2: the integration-level pin across ALL renderer work (typography
  // baseline, element overrides, not-prose boundaries, nested-callout re-parse,
  // accent-token migration). It renders the operator's ACTUAL offending page
  // (LFQ_FIXTURE above) and asserts the COMPLETE structural shape. Each
  // assertion is tagged [structural] (jsdom proves it directly) or
  // [readability→eyeball] (jsdom proves the precondition; legibility is the
  // operator's §8.1/§9 gate). RT-1 BLOCKING: the module-scoped shortcode state
  // maps are reset before each case so the tab/collapsible defaults are sound.
  beforeEach(() => __resetCanvasShortcodeState())

  it('renders the full prose + table + tabs + nested-callout hierarchy with the exact structural shape', async () => {
    const { container } = render(<CanvasRender content={LFQ_FIXTURE} />)
    // The async <tabs> dispatch settles before the structural assertions.
    await screen.findAllByTestId('tabs')

    // --- Prose structure [readability→eyeball] ---
    // The plugin baseline renders the heading hierarchy and lists. jsdom proves
    // the elements are present (the structural precondition for legibility);
    // the rhythm itself is the eyeball step. Exact heading inventory: one page
    // <h1> and the four section <h2>s in document order — a regression that
    // dropped a section heading or mis-leveled one fails this exact-equality.
    expect(Array.from(container.querySelectorAll('h1'), (h) => h.textContent)).toEqual([
      'Phase 1.5 — Batch 2',
    ])
    expect(Array.from(container.querySelectorAll('h2'), (h) => h.textContent)).toEqual([
      'Q4. CI matrix scope',
      'Q5. Nimony cell mode + scope expectations',
      'Q6. Iterator + async integration scope',
      'Reply format',
    ])
    // Four `---` thematic breaks separate the sections.
    expect(container.querySelectorAll('hr')).toHaveLength(4)

    // --- Callouts: the context callout + 3 nested-in-tab callouts [structural] ---
    // Exactly four callouts render, with their types in document order:
    // top-level "Context recap" (note), then the tip/note/tip callouts nested
    // inside the active tab panels of Q4/Q5/Q6. The nested ones prove the
    // "tabbed options with nested callouts" composition reaches the renderer.
    const callouts = container.querySelectorAll('[data-testid="callout"]')
    expect(
      Array.from(callouts, (c) => c.getAttribute('data-callout-type')),
    ).toEqual(['note', 'tip', 'note', 'tip'])
    // Every callout body carries not-prose (the §2.4 boundary), so the prose
    // cascade never reaches the re-parsed callout content. Assert the COMPLETE
    // class set on each body (Level 5, { exact: true }).
    callouts.forEach((callout) => {
      const body = callout.querySelectorAll('div')[1]
      expect(body).toHaveClass('not-prose text-sm text-text-primary', {
        exact: true,
      })
    })

    // --- Tables: GFM pipe tables with the override class set [structural] ---
    // Two tables (Q4 source-repo matrix, Q6 tier matrix). Each carries the
    // complete `table` override class set; a dropped/added token fails.
    const tables = container.querySelectorAll('table')
    expect(tables).toHaveLength(2)
    tables.forEach((table) => {
      expect(table).toHaveClass(
        'not-prose w-full border-collapse border border-bg-border my-3',
        { exact: true },
      )
    })
    // The Q4 table header row is exactly its four columns, in order — pins that
    // the GFM parse produced the right header cells with the override styling.
    const firstTableHeaders = tables[0].querySelectorAll('th')
    expect(Array.from(firstTableHeaders, (h) => h.textContent)).toEqual([
      'Repo',
      'OS rows',
      'Nim',
      'Sanitizers',
    ])
    firstTableHeaders.forEach((th) => {
      expect(th).toHaveClass(
        'border border-bg-border bg-bg-elevated px-3 py-1.5 text-left font-mono text-xs uppercase tracking-widest text-text-secondary',
        { exact: true },
      )
    })

    // --- Tabs: one <tabs> per question, four <tab>s each, active panel rendered [structural] ---
    // Three <tabs> blocks (Q4/Q5/Q6). Twelve tab buttons total (4 per block).
    // Three active tab panels (one per block), each carrying the not-prose
    // panel class set.
    expect(container.querySelectorAll('[data-testid="tabs"]')).toHaveLength(3)
    expect(container.querySelectorAll('[role="tab"]')).toHaveLength(12)
    const panels = container.querySelectorAll('[role="tabpanel"]')
    expect(panels).toHaveLength(3)
    panels.forEach((panel) => {
      expect(panel).toHaveClass('not-prose p-3 text-sm text-text-primary', {
        exact: true,
      })
    })
    // The Q4 tab bar's four option titles, in authored order — the recommended
    // option is first. Pins the per-option tab buttons survive the parse.
    const q4Tabs = container
      .querySelectorAll('[data-testid="tabs"]')[0]
      .querySelectorAll('[role="tab"]')
    expect(Array.from(q4Tabs, (t) => t.textContent)).toEqual([
      'A. Union + extras (Recommended)',
      'B. Trim to core',
      'C. Union but defer leak detectors',
      'D. Custom',
    ])

    // --- Nested callout inside the active tab panel [structural] ---
    // The Q4 active panel (option A) contains the "Why Valgrind plus Helgrind"
    // tip callout — the canonical nested composition that the styling collapse
    // flattened. Assert the nested callout is INSIDE the first panel and is the
    // tip variant.
    const nestedInFirstPanel = panels[0].querySelector('[data-testid="callout"]')
    expect(nestedInFirstPanel).not.toBeNull()
    expect(nestedInFirstPanel?.getAttribute('data-callout-type')).toBe('tip')

    // --- accent token migration [structural] ---
    // ZERO `accent-yellow` anywhere in the rendered output — the migration to
    // the defined `accent-amber` token left no undefined-token reference. This
    // scans the whole rendered subtree's classList (not a comment-tolerant
    // substring scan), so a single leaked element class would fail.
    const allTokens = Array.from(container.querySelectorAll('*')).flatMap((el) =>
      Array.from(el.classList),
    )
    expect(allTokens.filter((t) => t === 'accent-yellow')).toEqual([])

    // --- prose scope [structural] ---
    // CanvasRender's OWN output carries no `prose`/`prose-invert` token (that
    // wrapper is CanvasDetail's responsibility, §8.2). The shortcode regions
    // DO carry `not-prose`, asserted present so this scan cannot pass on an
    // empty render.
    expect(allTokens.filter((t) => t === 'prose')).toEqual([])
    expect(allTokens.filter((t) => t === 'prose-invert')).toEqual([])
    expect(allTokens).toContain('not-prose')
  })
})
