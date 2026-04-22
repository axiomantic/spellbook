import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { createElement } from 'react'
import { MetricCard } from './MetricCard'

describe('MetricCard', () => {
  it('renders the label in uppercase mono styling', () => {
    render(createElement(MetricCard, { label: 'Success Rate', value: 0.98 }))

    const label = screen.getByText('Success Rate')
    expect(label.className).toContain('font-mono')
    expect(label.className).toContain('uppercase')
    expect(label.className).toContain('tracking-widest')
  })

  it('renders a numeric value as its string representation', () => {
    render(createElement(MetricCard, { label: 'Total', value: 42 }))

    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders a string value as-is', () => {
    render(createElement(MetricCard, { label: 'Status', value: 'healthy' }))

    expect(screen.getByText('healthy')).toBeInTheDocument()
  })

  it('renders em-dash when value is null', () => {
    render(createElement(MetricCard, { label: 'P95 Latency', value: null }))

    expect(screen.getByText('\u2014')).toBeInTheDocument()
  })

  it('does not render unit when value is null', () => {
    render(
      createElement(MetricCard, { label: 'P95 Latency', value: null, unit: 'ms' })
    )

    expect(screen.queryByText('ms')).toBeNull()
    expect(screen.getByText('\u2014')).toBeInTheDocument()
  })

  it('renders unit alongside value when provided', () => {
    render(
      createElement(MetricCard, { label: 'P95 Latency', value: 125, unit: 'ms' })
    )

    expect(screen.getByText('125')).toBeInTheDocument()
    expect(screen.getByText('ms')).toBeInTheDocument()
  })

  it('applies default variant styling when variant is omitted', () => {
    const { container } = render(
      createElement(MetricCard, { label: 'Total', value: 10 })
    )

    const valueEl = container.querySelector('[data-testid="metric-card-value"]')
    expect(valueEl).not.toBeNull()
    expect(valueEl!.className).toContain('text-text-primary')
  })

  it('applies success variant styling', () => {
    const { container } = render(
      createElement(MetricCard, { label: 'Rate', value: 0.99, variant: 'success' })
    )

    const valueEl = container.querySelector('[data-testid="metric-card-value"]')
    expect(valueEl!.className).toContain('text-accent-green')
  })

  it('applies warning variant styling', () => {
    const { container } = render(
      createElement(MetricCard, { label: 'Rate', value: 0.5, variant: 'warning' })
    )

    const valueEl = container.querySelector('[data-testid="metric-card-value"]')
    expect(valueEl!.className).toContain('text-accent-amber')
  })

  it('applies error variant styling', () => {
    const { container } = render(
      createElement(MetricCard, { label: 'Rate', value: 0.2, variant: 'error' })
    )

    const valueEl = container.querySelector('[data-testid="metric-card-value"]')
    expect(valueEl!.className).toContain('text-accent-red')
  })

  it('uses the shared card class for the wrapper', () => {
    const { container } = render(
      createElement(MetricCard, { label: 'Total', value: 10 })
    )

    const card = container.firstChild as HTMLElement
    expect(card.className).toContain('card')
  })
})
