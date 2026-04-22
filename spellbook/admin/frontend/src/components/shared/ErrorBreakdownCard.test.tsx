import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { createElement } from 'react'
import { ErrorBreakdownCard } from './ErrorBreakdownCard'

describe('ErrorBreakdownCard', () => {
  it('renders "No errors" message when breakdown is null', () => {
    render(createElement(ErrorBreakdownCard, { breakdown: null }))

    expect(screen.getByText('No errors')).toBeInTheDocument()
  })

  it('renders "No errors" message when breakdown is empty', () => {
    render(createElement(ErrorBreakdownCard, { breakdown: {} }))

    expect(screen.getByText('No errors')).toBeInTheDocument()
  })

  it('renders errors sorted by count descending (most common first)', () => {
    const breakdown = {
      'timeout': 3,
      'connection_refused': 10,
      'invalid_json': 5,
    }

    const { container } = render(
      createElement(ErrorBreakdownCard, { breakdown })
    )

    const rows = container.querySelectorAll('[data-testid="error-breakdown-row"]')
    expect(rows.length).toBe(3)

    const labels = Array.from(rows).map(
      (r) => r.querySelector('[data-testid="error-label"]')?.textContent
    )
    const counts = Array.from(rows).map(
      (r) => r.querySelector('[data-testid="error-count"]')?.textContent
    )

    expect(labels).toEqual(['connection_refused', 'invalid_json', 'timeout'])
    expect(counts).toEqual(['10', '5', '3'])
  })

  it('renders a single entry correctly', () => {
    const { container } = render(
      createElement(ErrorBreakdownCard, { breakdown: { 'oom': 7 } })
    )

    const rows = container.querySelectorAll('[data-testid="error-breakdown-row"]')
    expect(rows.length).toBe(1)

    expect(screen.getByText('oom')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('preserves the exact input counts without aggregation', () => {
    const breakdown = { 'a': 1, 'b': 2 }

    render(createElement(ErrorBreakdownCard, { breakdown }))

    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('uses the shared card class for the wrapper', () => {
    const { container } = render(
      createElement(ErrorBreakdownCard, { breakdown: null })
    )

    const card = container.firstChild as HTMLElement
    expect(card.className).toContain('card')
  })

  it('applies mono label-style heading', () => {
    render(createElement(ErrorBreakdownCard, { breakdown: null }))

    const heading = screen.getByText('Error Breakdown')
    expect(heading.className).toContain('font-mono')
    expect(heading.className).toContain('uppercase')
  })
})
