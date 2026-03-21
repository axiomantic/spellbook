import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { createElement } from 'react'
import { Pagination } from './Pagination'

// Helper to render Pagination with defaults
function renderPagination(overrides: Record<string, unknown> = {}) {
  const defaults = {
    page: 3,
    pages: 10,
    total: 250,
    onPageChange: vi.fn(),
  }
  const props = { ...defaults, ...overrides }
  const result = render(createElement(Pagination, props as never))
  return { ...result, props }
}

describe('Pagination', () => {
  describe('backward compatibility (compact mode)', () => {
    it('renders compact layout when only original props are passed', () => {
      const onPageChange = vi.fn()
      render(
        createElement(Pagination, {
          page: 2,
          pages: 5,
          total: 100,
          onPageChange,
        })
      )

      // Should show the item count text
      expect(screen.getByText('100 items / page 2 of 5')).toBeInTheDocument()

      // Should have Prev and Next buttons
      expect(screen.getByRole('button', { name: 'Prev' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()

      // Should NOT have page number buttons (compact mode)
      expect(screen.queryByRole('button', { name: '1' })).not.toBeInTheDocument()
    })

    it('disables Prev button on first page', () => {
      renderPagination({ page: 1, pages: 5 })
      expect(screen.getByRole('button', { name: 'Prev' })).toBeDisabled()
    })

    it('disables Next button on last page', () => {
      renderPagination({ page: 5, pages: 5 })
      expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
    })

    it('calls onPageChange with page-1 when Prev is clicked', async () => {
      const user = userEvent.setup()
      const { props } = renderPagination({ page: 3, pages: 5 })

      await user.click(screen.getByRole('button', { name: 'Prev' }))
      expect(props.onPageChange).toHaveBeenCalledTimes(1)
      expect(props.onPageChange).toHaveBeenCalledWith(2)
    })

    it('calls onPageChange with page+1 when Next is clicked', async () => {
      const user = userEvent.setup()
      const { props } = renderPagination({ page: 3, pages: 5 })

      await user.click(screen.getByRole('button', { name: 'Next' }))
      expect(props.onPageChange).toHaveBeenCalledTimes(1)
      expect(props.onPageChange).toHaveBeenCalledWith(4)
    })

    it('renders compact mode when compact prop is explicitly true', () => {
      renderPagination({ compact: true, page: 3, pages: 10 })

      // Compact mode: no page number buttons
      expect(screen.queryByRole('button', { name: '1' })).not.toBeInTheDocument()
      expect(screen.getByText('250 items / page 3 of 10')).toBeInTheDocument()
    })
  })

  describe('full mode with page buttons', () => {
    it('renders page number buttons when compact is false', () => {
      renderPagination({ compact: false, page: 5, pages: 10 })

      // Should show: 1 ... 4 5 6 ... 10
      expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '4' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '5' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '6' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '10' })).toBeInTheDocument()

      // Pages not in the neighbor window should not appear
      expect(screen.queryByRole('button', { name: '3' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: '7' })).not.toBeInTheDocument()
    })

    it('renders ellipsis between non-adjacent page groups', () => {
      const { container } = renderPagination({ compact: false, page: 5, pages: 10 })

      // Should have ellipsis indicators
      const ellipses = container.querySelectorAll('[data-testid="pagination-ellipsis"]')
      expect(ellipses).toHaveLength(2)
      expect(ellipses[0].textContent).toBe('...')
      expect(ellipses[1].textContent).toBe('...')
    })

    it('does not render leading ellipsis when current page is near start', () => {
      const { container } = renderPagination({ compact: false, page: 2, pages: 10 })

      // Page 2: show 1 2 3 ... 10 (no leading ellipsis)
      expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '3' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '10' })).toBeInTheDocument()

      const ellipses = container.querySelectorAll('[data-testid="pagination-ellipsis"]')
      expect(ellipses).toHaveLength(1) // only trailing ellipsis
    })

    it('does not render trailing ellipsis when current page is near end', () => {
      const { container } = renderPagination({ compact: false, page: 9, pages: 10 })

      // Page 9: show 1 ... 8 9 10 (no trailing ellipsis)
      expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '8' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '9' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '10' })).toBeInTheDocument()

      const ellipses = container.querySelectorAll('[data-testid="pagination-ellipsis"]')
      expect(ellipses).toHaveLength(1) // only leading ellipsis
    })

    it('highlights the active page with accent-green styling', () => {
      renderPagination({ compact: false, page: 5, pages: 10 })

      const activeButton = screen.getByRole('button', { name: '5' })
      expect(activeButton.className).toContain('text-accent-green')
    })

    it('calls onPageChange when a page number button is clicked', async () => {
      const user = userEvent.setup()
      const { props } = renderPagination({ compact: false, page: 5, pages: 10 })

      await user.click(screen.getByRole('button', { name: '1' }))
      expect(props.onPageChange).toHaveBeenCalledTimes(1)
      expect(props.onPageChange).toHaveBeenCalledWith(1)
    })

    it('does not render page buttons when there is only 1 page', () => {
      renderPagination({ compact: false, page: 1, pages: 1 })

      // With only 1 page, no page buttons needed
      expect(screen.queryByRole('button', { name: '1' })).not.toBeInTheDocument()
    })

    it('renders all pages without ellipsis when pages <= 5', () => {
      const { container } = renderPagination({ compact: false, page: 2, pages: 4 })

      // All pages should be visible: 1 2 3 4
      expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '3' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '4' })).toBeInTheDocument()

      const ellipses = container.querySelectorAll('[data-testid="pagination-ellipsis"]')
      expect(ellipses).toHaveLength(0)
    })
  })

  describe('page size selector', () => {
    it('renders page size chips when showPageSize is true', () => {
      renderPagination({
        compact: false,
        showPageSize: true,
        perPage: 50,
        onPerPageChange: vi.fn(),
      })

      expect(screen.getByRole('button', { name: '25' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '50' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '100' })).toBeInTheDocument()
    })

    it('highlights the active page size with accent-green styling', () => {
      renderPagination({
        compact: false,
        showPageSize: true,
        perPage: 50,
        onPerPageChange: vi.fn(),
      })

      const activeChip = screen.getByRole('button', { name: '50' })
      expect(activeChip.className).toContain('text-accent-green')
    })

    it('calls onPerPageChange when a page size chip is clicked', async () => {
      const user = userEvent.setup()
      const onPerPageChange = vi.fn()
      renderPagination({
        compact: false,
        showPageSize: true,
        perPage: 50,
        onPerPageChange,
      })

      await user.click(screen.getByRole('button', { name: '100' }))
      expect(onPerPageChange).toHaveBeenCalledTimes(1)
      expect(onPerPageChange).toHaveBeenCalledWith(100)
    })

    it('uses custom pageSizeOptions when provided', () => {
      renderPagination({
        compact: false,
        showPageSize: true,
        perPage: 15,
        onPerPageChange: vi.fn(),
        pageSizeOptions: [15, 30, 75],
        page: 1,
        pages: 1,
        total: 10,
      })

      expect(screen.getByRole('button', { name: '15' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '30' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '75' })).toBeInTheDocument()
      // 25 and 100 from defaults should NOT appear
      expect(screen.queryByRole('button', { name: '25' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: '100' })).not.toBeInTheDocument()
    })

    it('does not render page size selector when showPageSize is false', () => {
      const { container } = renderPagination({
        compact: false,
        showPageSize: false,
      })

      const pageSizeSection = container.querySelector('[data-testid="page-size-selector"]')
      expect(pageSizeSection).not.toBeInTheDocument()
    })
  })

  describe('show total', () => {
    it('renders total count when showTotal is true', () => {
      renderPagination({
        compact: false,
        showTotal: true,
        total: 250,
      })

      expect(screen.getByText('250 items')).toBeInTheDocument()
    })

    it('does not render total section when showTotal is false in full mode', () => {
      renderPagination({
        compact: false,
        showTotal: false,
      })

      // The compact-style "X items / page Y of Z" should not appear
      expect(screen.queryByText(/250 items/)).not.toBeInTheDocument()
    })
  })

  describe('jump to page', () => {
    it('renders a jump-to-page input when showJumpToPage is true', () => {
      renderPagination({
        compact: false,
        showJumpToPage: true,
        pages: 10,
      })

      const input = screen.getByRole('spinbutton', { name: /go to page/i })
      expect(input).toBeInTheDocument()
    })

    it('navigates to entered page on Enter key', async () => {
      const user = userEvent.setup()
      const { props } = renderPagination({
        compact: false,
        showJumpToPage: true,
        pages: 10,
      })

      const input = screen.getByRole('spinbutton', { name: /go to page/i })
      await user.clear(input)
      await user.type(input, '7{Enter}')

      expect(props.onPageChange).toHaveBeenCalledWith(7)
    })

    it('clamps jump-to-page value to valid range', async () => {
      const user = userEvent.setup()
      const { props } = renderPagination({
        compact: false,
        showJumpToPage: true,
        pages: 10,
      })

      const input = screen.getByRole('spinbutton', { name: /go to page/i })
      await user.clear(input)
      await user.type(input, '99{Enter}')

      expect(props.onPageChange).toHaveBeenCalledWith(10) // clamped to max

      await user.clear(input)
      await user.type(input, '0{Enter}')

      expect(props.onPageChange).toHaveBeenCalledWith(1) // clamped to min
    })

    it('does not render jump-to-page input when showJumpToPage is false', () => {
      renderPagination({
        compact: false,
        showJumpToPage: false,
      })

      expect(screen.queryByRole('spinbutton', { name: /go to page/i })).not.toBeInTheDocument()
    })
  })

  describe('styling', () => {
    it('uses font-mono and text-xs on the container', () => {
      const { container } = renderPagination({ compact: false })

      const wrapper = container.firstElementChild as HTMLElement
      expect(wrapper.className).toContain('font-mono')
      expect(wrapper.className).toContain('text-xs')
    })

    it('uses border-bg-border on page buttons', () => {
      renderPagination({ compact: false, page: 3, pages: 10 })

      const pageButton = screen.getByRole('button', { name: '3' })
      expect(pageButton.className).toContain('border')
    })
  })
})
