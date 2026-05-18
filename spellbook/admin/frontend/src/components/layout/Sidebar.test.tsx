import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from './Sidebar'

// Mock useDashboard to avoid real API calls
vi.mock('../../hooks/useDashboard', () => ({
  useDashboard: vi.fn(() => ({ data: undefined })),
}))

function renderSidebar() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(MemoryRouter, null, createElement(Sidebar))
    )
  )
}

describe('Sidebar', () => {
  describe('navigation items after FocusPage split', () => {
    it('renders a Stacks nav link pointing to /stacks', () => {
      renderSidebar()

      const stacksLink = screen.getByText('// STACKS')
      expect(stacksLink).toBeInTheDocument()
      expect(stacksLink.closest('a')).toHaveAttribute('href', '/stacks')
    })

    it('renders a Corrections nav link pointing to /corrections', () => {
      renderSidebar()

      const correctionsLink = screen.getByText('// CORRECTIONS')
      expect(correctionsLink).toBeInTheDocument()
      expect(correctionsLink.closest('a')).toHaveAttribute('href', '/corrections')
    })

    it('does not render a Focus nav link', () => {
      renderSidebar()

      expect(screen.queryByText('// FOCUS')).not.toBeInTheDocument()
    })
  })

  describe('canvas nav link', () => {
    it('renders a Canvas nav link pointing to /canvas', () => {
      renderSidebar()

      const canvasLink = screen.getByText('// CANVAS')
      expect(canvasLink).toBeInTheDocument()
      expect(canvasLink.closest('a')).toHaveAttribute('href', '/canvas')
    })

    it('places // CANVAS between // MEMORY and // SECURITY', () => {
      const { container } = renderSidebar()
      const labels = Array.from(
        container.querySelectorAll('nav a'),
      ).map((el) => el.textContent)

      const memoryIdx = labels.indexOf('// MEMORY')
      const canvasIdx = labels.indexOf('// CANVAS')
      const securityIdx = labels.indexOf('// SECURITY')

      expect(memoryIdx).toBeGreaterThanOrEqual(0)
      expect(canvasIdx).toBeGreaterThan(memoryIdx)
      expect(securityIdx).toBeGreaterThan(canvasIdx)
    })
  })
})
