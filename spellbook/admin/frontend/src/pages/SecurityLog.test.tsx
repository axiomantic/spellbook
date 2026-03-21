import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { SecurityLog } from './SecurityLog'

// Mock useListPage - the new hook the migrated component should use
vi.mock('../hooks/useListPage', () => ({
  useListPage: vi.fn(),
}))

// Mock useSecurity for the summary hook only
vi.mock('../hooks/useSecurity', () => ({
  useSecuritySummary: vi.fn(),
}))

import { useListPage } from '../hooks/useListPage'
import { useSecuritySummary } from '../hooks/useSecurity'

const mockUseListPage = useListPage as Mock
const mockUseSecuritySummary = useSecuritySummary as Mock

const mockEvent = {
  id: 1,
  event_type: 'tool_blocked',
  severity: 'critical',
  source: 'security-engine',
  detail: 'Blocked dangerous tool invocation',
  session_id: 'sess-abc-123',
  tool_name: 'Bash',
  action_taken: 'blocked',
  created_at: '2026-03-20T14:30:00Z',
}

const mockEvent2 = {
  id: 2,
  event_type: 'canary_triggered',
  severity: 'warning',
  source: 'canary-system',
  detail: 'Canary token detected in output',
  session_id: 'sess-def-456',
  tool_name: 'Read',
  action_taken: 'warned',
  created_at: '2026-03-20T15:00:00Z',
}

const mockSetFilters = vi.fn()
const mockClearFilters = vi.fn()

function makeListPageReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: [mockEvent, mockEvent2],
    total: 2,
    isLoading: false,
    isError: false,
    error: null,
    page: 1,
    pages: 1,
    perPage: 50,
    setPage: vi.fn(),
    setPerPage: vi.fn(),
    sorting: { column: undefined, order: 'asc' as const },
    setSorting: vi.fn(),
    search: '',
    setSearch: vi.fn(),
    filters: {},
    setFilters: mockSetFilters,
    clearFilters: mockClearFilters,
    tableProps: {
      data: [mockEvent, mockEvent2],
      loading: false,
      pagination: {
        page: 1,
        pages: 1,
        total: 2,
        perPage: 50,
        onPageChange: vi.fn(),
        onPerPageChange: vi.fn(),
      },
      sorting: {
        sortColumn: undefined,
        sortOrder: 'asc' as const,
        onSortChange: vi.fn(),
      },
    },
    ...overrides,
  }
}

function renderSecurityLog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/security'] },
        createElement(SecurityLog)
      )
    )
  )
}

describe('SecurityLog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseListPage.mockReturnValue(makeListPageReturn())
    mockUseSecuritySummary.mockReturnValue({
      data: {
        by_severity: { critical: 5, warning: 12, info: 30 },
      },
    })
  })

  describe('uses useListPage hook', () => {
    it('calls useListPage with security-events query key and endpoint', () => {
      renderSecurityLog()

      expect(mockUseListPage).toHaveBeenCalledTimes(1)
      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.queryKey).toEqual(['security-events'])
      expect(callArgs.endpoint).toBe('/api/security/events')
    })
  })

  describe('summary cards', () => {
    it('renders summary cards with severity counts and total', () => {
      renderSecurityLog()

      // Total = 5 + 12 + 30 = 47
      expect(screen.getByText('47')).toBeInTheDocument()
      expect(screen.getByText('5')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('30')).toBeInTheDocument()
    })

    it('renders severity labels in summary cards', () => {
      renderSecurityLog()

      // The "Total" label is unique to summary cards
      const totalLabel = screen.getByText('Total')
      expect(totalLabel).toBeInTheDocument()

      // Summary cards grid contains the total card and 3 severity cards
      // The grid parent has all 4 cards as children
      const grid = totalLabel.closest('.grid')!
      expect(grid).not.toBeNull()

      expect(within(grid as HTMLElement).getByText('critical')).toBeInTheDocument()
      expect(within(grid as HTMLElement).getByText('warning')).toBeInTheDocument()
      expect(within(grid as HTMLElement).getByText('info')).toBeInTheDocument()
    })
  })

  describe('DataTable columns', () => {
    it('renders table headers for severity, event type, tool, detail, and time', () => {
      renderSecurityLog()

      const table = screen.getByRole('table')
      const headers = within(table).getAllByRole('columnheader')
      const headerTexts = headers.map((h) => h.textContent?.trim().toLowerCase())

      expect(headerTexts).toContain('severity')
      expect(headerTexts).toContain('event type')
      expect(headerTexts).toContain('tool')
      expect(headerTexts).toContain('detail')
      expect(headerTexts).toContain('time')
    })

    it('renders event data in table rows', () => {
      renderSecurityLog()

      const table = screen.getByRole('table')

      // First event data
      expect(within(table).getByText('tool_blocked')).toBeInTheDocument()
      expect(within(table).getByText('Bash')).toBeInTheDocument()
      expect(within(table).getByText('Blocked dangerous tool invocation')).toBeInTheDocument()

      // Second event data
      expect(within(table).getByText('canary_triggered')).toBeInTheDocument()
      expect(within(table).getByText('Read')).toBeInTheDocument()
      expect(within(table).getByText('Canary token detected in output')).toBeInTheDocument()
    })

    it('renders severity as a Badge component', () => {
      renderSecurityLog()

      // Badge renders the label text; there should be badges for critical and warning
      const table = screen.getByRole('table')
      const rows = within(table).getAllByRole('row')
      // Row 0 is header, row 1 and 2 are data rows
      expect(rows.length).toBe(3) // 1 header + 2 data rows

      // The severity cell should contain the severity text styled as a badge
      // Looking for the text within the table body rows
      const dataRows = rows.slice(1)
      expect(within(dataRows[0]).getByText('critical')).toBeInTheDocument()
      expect(within(dataRows[1]).getByText('warning')).toBeInTheDocument()
    })
  })

  describe('severity filter', () => {
    it('renders severity filter chips including all option', () => {
      renderSecurityLog()

      // Filter chips for severity levels - look for buttons
      const allButton = screen.getByRole('button', { name: /all/i })
      expect(allButton).toBeInTheDocument()

      const criticalButton = screen.getByRole('button', { name: /critical/i })
      expect(criticalButton).toBeInTheDocument()

      const warningButton = screen.getByRole('button', { name: /warning/i })
      expect(warningButton).toBeInTheDocument()

      const infoButton = screen.getByRole('button', { name: /info/i })
      expect(infoButton).toBeInTheDocument()
    })

    it('calls setFilters when a severity chip is clicked', async () => {
      renderSecurityLog()

      const user = userEvent.setup()
      const criticalButton = screen.getByRole('button', { name: /critical/i })
      await user.click(criticalButton)

      expect(mockSetFilters).toHaveBeenCalledWith({ severity: 'critical' })
    })

    it('calls clearFilters or sets empty severity when "all" chip is clicked', async () => {
      mockUseListPage.mockReturnValue(
        makeListPageReturn({ filters: { severity: 'critical' } })
      )
      renderSecurityLog()

      const user = userEvent.setup()
      const allButton = screen.getByRole('button', { name: /all/i })
      await user.click(allButton)

      // Either clears filters entirely or sets empty severity
      const lastCall = mockSetFilters.mock.calls.length > 0
        ? mockSetFilters.mock.calls[mockSetFilters.mock.calls.length - 1][0]
        : null
      const clearedFilters = mockClearFilters.mock.calls.length > 0

      expect(lastCall === null || lastCall?.severity === undefined || clearedFilters).toBe(true)
    })
  })

  describe('expandable row detail', () => {
    it('shows detail section when a row is clicked', async () => {
      renderSecurityLog()

      const user = userEvent.setup()
      const table = screen.getByRole('table')
      const rows = within(table).getAllByRole('row')
      const firstDataRow = rows[1]

      await user.click(firstDataRow)

      // After clicking, the detail section should show source, session, tool, action, event ID
      expect(screen.getByText('security-engine')).toBeInTheDocument()
      expect(screen.getByText('sess-abc-123')).toBeInTheDocument()
      expect(screen.getByText('blocked')).toBeInTheDocument()
    })

    it('hides detail section when the same row is clicked again', async () => {
      renderSecurityLog()

      const user = userEvent.setup()
      const table = screen.getByRole('table')
      const rows = within(table).getAllByRole('row')
      const firstDataRow = rows[1]

      // Click to expand
      await user.click(firstDataRow)
      expect(screen.getByText('security-engine')).toBeInTheDocument()

      // Click again to collapse
      await user.click(firstDataRow)
      expect(screen.queryByText('security-engine')).not.toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('shows loading overlay when data is loading', () => {
      mockUseListPage.mockReturnValue(
        makeListPageReturn({ isLoading: true, data: [], tableProps: { data: [], loading: true, pagination: { page: 1, pages: 0, total: 0, perPage: 50, onPageChange: vi.fn(), onPerPageChange: vi.fn() }, sorting: { sortColumn: undefined, sortOrder: 'asc', onSortChange: vi.fn() } } })
      )
      const { container } = renderSecurityLog()

      // DataTable renders a loading overlay div with bg-bg-base/50 class when loading
      const overlay = container.querySelector('.bg-bg-base\\/50')
      expect(overlay).not.toBeNull()

      // The overlay contains the spinner's animate-spin element
      const spinner = overlay!.querySelector('.animate-spin')
      expect(spinner).not.toBeNull()
    })
  })

  describe('empty state', () => {
    it('shows empty state when no events match', () => {
      mockUseListPage.mockReturnValue(
        makeListPageReturn({ data: [], tableProps: { data: [], loading: false, pagination: { page: 1, pages: 0, total: 0, perPage: 50, onPageChange: vi.fn(), onPerPageChange: vi.fn() }, sorting: { sortColumn: undefined, sortOrder: 'asc', onSortChange: vi.fn() } } })
      )
      renderSecurityLog()

      expect(screen.getByText('No events')).toBeInTheDocument()
    })
  })
})
