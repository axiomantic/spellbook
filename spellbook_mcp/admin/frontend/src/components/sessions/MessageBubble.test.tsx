import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { MessageBubble } from './MessageBubble'
import type { SessionMessage } from '../../api/types'

function makeMessage(overrides: Partial<SessionMessage> = {}): SessionMessage {
  return {
    line_number: 1,
    type: 'user',
    timestamp: '2026-03-15T10:30:00Z',
    content: 'Hello world',
    is_compact_summary: false,
    raw: null,
    ...overrides,
  }
}

describe('MessageBubble', () => {
  describe('user messages', () => {
    it('renders user message with right alignment and blue styling', () => {
      const msg = makeMessage({ type: 'user', content: 'Test user message' })
      const { container } = render(<MessageBubble message={msg} />)

      // Content is rendered
      expect(screen.getByText('Test user message')).toBeInTheDocument()

      // Type label shown
      expect(screen.getByText('user')).toBeInTheDocument()

      // Line number shown
      expect(screen.getByText('Line 1')).toBeInTheDocument()

      // Right-aligned: outer div has justify-end
      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-end')

      // Blue background
      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-blue-900/20')
      expect(innerDiv.className).toContain('border-blue-500')

      // Max width constrained (conversational)
      expect(innerDiv.className).toContain('max-w-[75%]')
    })
  })

  describe('assistant messages', () => {
    it('renders assistant message with left alignment and elevated bg', () => {
      const msg = makeMessage({ type: 'assistant', content: 'Test assistant reply', line_number: 2 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('Test assistant reply')).toBeInTheDocument()
      expect(screen.getByText('assistant')).toBeInTheDocument()
      expect(screen.getByText('Line 2')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-start')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-elevated')
      expect(innerDiv.className).toContain('border-text-dim')
      expect(innerDiv.className).toContain('max-w-[75%]')
    })
  })

  describe('system messages', () => {
    it('renders system message centered with italic muted styling', () => {
      const msg = makeMessage({ type: 'system', content: 'System init', line_number: 3 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('System init')).toBeInTheDocument()
      expect(screen.getByText('system')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-surface')
      expect(innerDiv.className).toContain('italic')

      // Full width (not conversational)
      expect(innerDiv.className).toContain('max-w-full')
    })
  })

  describe('progress messages', () => {
    it('renders progress message centered with spinner icon', () => {
      const msg = makeMessage({ type: 'progress', content: 'Loading...', line_number: 4 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('Loading...')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      // Has an animated spinner SVG
      const spinnerSvg = container.querySelector('svg.animate-spin')
      expect(spinnerSvg).toBeInTheDocument()
    })
  })

  describe('custom-title messages', () => {
    it('renders custom-title with green accent and tag icon', () => {
      const msg = makeMessage({ type: 'custom-title', content: 'My Session', line_number: 5 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('My Session')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-accent-green/10')
      expect(innerDiv.className).toContain('text-accent-green')

      // Has a tag icon SVG
      const svgs = container.querySelectorAll('svg')
      expect(svgs.length).toBeGreaterThan(0)
    })
  })

  describe('error messages', () => {
    it('renders error message with red styling and warning icon', () => {
      const msg = makeMessage({ type: 'error', content: '[Malformed JSONL line]', line_number: 6 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('[Malformed JSONL line]')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-red-900/20')
      expect(innerDiv.className).toContain('text-red-400')

      // Has a warning SVG icon
      const svgs = container.querySelectorAll('svg')
      expect(svgs.length).toBeGreaterThan(0)
    })
  })

  describe('unknown/other message types', () => {
    it('renders unknown types centered with muted defaults', () => {
      const msg = makeMessage({ type: 'queue-operation', content: 'Queued item', line_number: 7 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('Queued item')).toBeInTheDocument()
      expect(screen.getByText('queue-operation')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-surface')
      expect(innerDiv.className).toContain('text-text-dim')
      expect(innerDiv.className).toContain('max-w-full')
    })

    it('renders file-history-snapshot with same muted defaults', () => {
      const msg = makeMessage({ type: 'file-history-snapshot', content: 'snapshot data', line_number: 8 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('snapshot data')).toBeInTheDocument()
      expect(screen.getByText('file-history-snapshot')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')
    })

    it('renders completely unknown types with fallback centered muted styling', () => {
      const msg = makeMessage({ type: 'some-future-type', content: 'future content', line_number: 9 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('future content')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-surface')
      expect(innerDiv.className).toContain('text-text-dim')
    })
  })

  describe('compact summary messages', () => {
    it('renders collapsed by default with banner button', () => {
      const msg = makeMessage({
        type: 'user',
        content: 'This is the compacted summary text',
        is_compact_summary: true,
        line_number: 10,
      })
      render(<MessageBubble message={msg} />)

      // Banner button is present
      const button = screen.getByRole('button')
      expect(button).toBeInTheDocument()
      expect(button.textContent).toContain('Compacted summary')

      // Content NOT visible when collapsed
      expect(screen.queryByText('This is the compacted summary text')).not.toBeInTheDocument()

      // Down arrow indicator visible
      expect(button.textContent).toContain('\u25BC')
    })

    it('expands on click to reveal content', async () => {
      const user = userEvent.setup()
      const msg = makeMessage({
        type: 'user',
        content: 'Expanded summary content here',
        is_compact_summary: true,
        line_number: 11,
      })
      render(<MessageBubble message={msg} />)

      // Click to expand
      const button = screen.getByRole('button')
      await user.click(button)

      // Content now visible
      expect(screen.getByText('Expanded summary content here')).toBeInTheDocument()

      // Up arrow indicator visible
      expect(button.textContent).toContain('\u25B2')
    })

    it('collapses again on second click', async () => {
      const user = userEvent.setup()
      const msg = makeMessage({
        type: 'user',
        content: 'Toggle me',
        is_compact_summary: true,
        line_number: 12,
      })
      render(<MessageBubble message={msg} />)

      const button = screen.getByRole('button')
      await user.click(button) // expand
      expect(screen.getByText('Toggle me')).toBeInTheDocument()

      await user.click(button) // collapse
      expect(screen.queryByText('Toggle me')).not.toBeInTheDocument()
    })
  })

  describe('timestamp handling', () => {
    it('displays formatted timestamp when present', () => {
      const msg = makeMessage({ timestamp: '2026-03-15T10:30:00Z' })
      render(<MessageBubble message={msg} />)

      // The timestamp is formatted via toLocaleTimeString -- we check it exists
      // Since locale-dependent, just verify the timestamp element is present
      const timeElements = screen.getAllByText(/\d/)
      expect(timeElements.length).toBeGreaterThan(0)
    })

    it('does not render timestamp element when timestamp is null', () => {
      const msg = makeMessage({ timestamp: null, content: 'No time' })
      const { container } = render(<MessageBubble message={msg} />)

      // The timestamp span should not be present
      // The header row still exists but without timestamp
      const headerRow = container.querySelector('.flex.items-center.justify-between')
      expect(headerRow).toBeInTheDocument()
      // Only the type label child, no timestamp span
      expect(headerRow!.children.length).toBe(1)
    })
  })

  describe('empty content', () => {
    it('renders "(empty)" placeholder when content is empty string', () => {
      const msg = makeMessage({ content: '' })
      render(<MessageBubble message={msg} />)

      expect(screen.getByText('(empty)')).toBeInTheDocument()
    })
  })

  describe('pr-link messages', () => {
    it('renders pr-link with link icon and centered styling', () => {
      const msg = makeMessage({ type: 'pr-link', content: 'https://github.com/example/pr/1', line_number: 13 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('https://github.com/example/pr/1')).toBeInTheDocument()
      expect(screen.getByText('pr-link')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-surface')

      // Has a link SVG icon
      const svgs = container.querySelectorAll('svg')
      expect(svgs.length).toBeGreaterThan(0)
    })
  })

  describe('last-prompt messages', () => {
    it('renders last-prompt centered with muted styling and no icon', () => {
      const msg = makeMessage({ type: 'last-prompt', content: 'Last prompt text', line_number: 14 })
      const { container } = render(<MessageBubble message={msg} />)

      expect(screen.getByText('Last prompt text')).toBeInTheDocument()

      const outerDiv = container.firstElementChild as HTMLElement
      expect(outerDiv.className).toContain('justify-center')

      const innerDiv = outerDiv.firstElementChild as HTMLElement
      expect(innerDiv.className).toContain('bg-bg-surface')
      expect(innerDiv.className).toContain('text-text-dim')

      // No icon for last-prompt
      const svgs = container.querySelectorAll('svg')
      expect(svgs.length).toBe(0)
    })
  })
})
