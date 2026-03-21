import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { CorrectionsPage } from './CorrectionsPage'
import type { CorrectionEvent, StintEntry } from '../api/types'

// Mock useListPage -- the hook is already tested; we test integration here
vi.mock('../hooks/useListPage', () => ({
  useListPage: vi.fn(),
}))

import { useListPage } from '../hooks/useListPage'

const mockUseListPage = useListPage as Mock

function makeStintEntry(overrides: Partial<StintEntry> = {}): StintEntry {
  return {
    name: 'develop',
    purpose: 'Build feature',
    behavioral_mode: 'autonomous',
    metadata: {},
    entered_at: '2026-03-15T10:00:00Z',
    ...overrides,
  }
}

function makeCorrection(overrides: Partial<CorrectionEvent> = {}): CorrectionEvent {
  return {
    id: 1,
    project_path: '/Users/alice/my-project',
    session_id: 'sess-abc',
    correction_type: 'llm_wrong',
    old_stack: [makeStintEntry({ name: 'old-skill' })],
    new_stack: [makeStintEntry({ name: 'new-skill' })],
    diff_summary: 'Replaced old-skill with new-skill',
    created_at: '2026-03-15T12:00:00Z',
    ...overrides,
  }
}

function makeUseListPageReturn(
  data: CorrectionEvent[],
  overrides: Record<string, unknown> = {}
) {
  return {
    data,
    total: data.length,
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
    filters: {} as Record<string, string>,
    setFilters: vi.fn(),
    clearFilters: vi.fn(),
    tableProps: {
      data,
      loading: false,
      pagination: {
        page: 1,
        pages: 1,
        total: data.length,
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

function renderCorrectionsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/corrections'] },
        createElement(CorrectionsPage)
      )
    )
  )
}

describe('CorrectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('useListPage integration', () => {
    it('calls useListPage with corrections endpoint and query key', () => {
      mockUseListPage.mockReturnValue(makeUseListPageReturn([]))

      renderCorrectionsPage()

      expect(mockUseListPage).toHaveBeenCalledTimes(1)
      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.queryKey).toEqual(['corrections'])
      expect(callArgs.endpoint).toBe('/api/focus/corrections')
    })

    /*
    ESCAPE: calls useListPage with corrections endpoint and query key
      CLAIM: CorrectionsPage invokes useListPage with the correct queryKey and endpoint
      PATH: CorrectionsPage -> useListPage({ queryKey: ['corrections'], endpoint: '/api/focus/corrections' })
      CHECK: callArgs.queryKey === ['corrections'] and callArgs.endpoint === '/api/focus/corrections'
      MUTATION: Wrong queryKey (e.g. ['focus', 'corrections']) would fail array equality; wrong endpoint would fail string equality
      ESCAPE: Other options (defaultPerPage, defaultSort) are not checked here but are tested implicitly by the page rendering correctly. A wrong defaultPerPage wouldn't break the page, just behavior.
      IMPACT: Wrong endpoint means fetching from wrong API; wrong queryKey means cache conflicts
    */
  })

  describe('loading state', () => {
    it('shows loading overlay when data is loading', () => {
      mockUseListPage.mockReturnValue(
        makeUseListPageReturn([], {
          isLoading: true,
          tableProps: {
            data: [],
            loading: true,
            pagination: {
              page: 1,
              pages: 0,
              total: 0,
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
        })
      )

      renderCorrectionsPage()

      // DataTable handles loading internally; verify the page renders without error
      // The DataTable renders a LoadingSpinner overlay when loading=true
      expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    })

    /*
    ESCAPE: shows loading overlay when data is loading
      CLAIM: When useListPage returns loading=true, page shows a loading spinner
      PATH: useListPage({isLoading: true}) -> DataTable({loading: true}) -> LoadingSpinner
      CHECK: animate-spin class element exists in DOM
      MUTATION: If loading wasn't passed to DataTable, spinner wouldn't render
      ESCAPE: Could render a spinner from somewhere else. But since we mock useListPage and the only spinner source is DataTable, this is reliable.
      IMPACT: Users would see blank screen while data loads
    */
  })

  describe('empty state', () => {
    it('shows empty state when no corrections exist', () => {
      mockUseListPage.mockReturnValue(makeUseListPageReturn([]))

      renderCorrectionsPage()

      expect(screen.getByText('No Corrections')).toBeInTheDocument()
    })

    /*
    ESCAPE: shows empty state when no corrections exist
      CLAIM: Empty data array renders an empty state message
      PATH: useListPage returns [] -> DataTable receives [] -> EmptyState renders
      CHECK: Text "No Corrections" appears in DOM
      MUTATION: Wrong emptyTitle would show different text, failing assertion
      ESCAPE: Nothing reasonable -- exact text match
      IMPACT: Users would see empty table instead of helpful message
    */
  })

  describe('column rendering', () => {
    it('renders correction data in table columns', () => {
      const correction = makeCorrection({
        id: 42,
        project_path: '/Users/alice/deep/nested/project',
        correction_type: 'llm_wrong',
        diff_summary: 'Fixed skill drift',
        created_at: '2026-03-15T12:00:00Z',
      })
      mockUseListPage.mockReturnValue(makeUseListPageReturn([correction]))

      renderCorrectionsPage()

      // Column headers
      expect(screen.getByText('Timestamp')).toBeInTheDocument()
      expect(screen.getByText('Project')).toBeInTheDocument()
      expect(screen.getByText('Type')).toBeInTheDocument()
      expect(screen.getByText('Diff Summary')).toBeInTheDocument()

      // Data cells - project path gets shortened
      expect(screen.getByText('nested/project')).toBeInTheDocument()
      // Correction type badge
      expect(screen.getByText('LLM')).toBeInTheDocument()
      // Diff summary
      expect(screen.getByText('Fixed skill drift')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders correction data in table columns
      CLAIM: Table shows column headers and cell data for corrections
      PATH: useListPage returns [correction] -> DataTable renders columns
      CHECK: Column headers (Timestamp, Project, Type, Diff Summary) present; cell values present (shortened path, badge label, diff_summary)
      MUTATION: Missing column definition would omit header; wrong accessor would show wrong data
      ESCAPE: Could render the text somewhere other than the table, but given the component structure, the text is from cell renderers
      IMPACT: Users would see wrong or missing data in table
    */

    it('renders mcp_wrong badge variant correctly', () => {
      const correction = makeCorrection({
        correction_type: 'mcp_wrong',
      })
      mockUseListPage.mockReturnValue(makeUseListPageReturn([correction]))

      renderCorrectionsPage()

      expect(screen.getByText('MCP')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders mcp_wrong badge variant correctly
      CLAIM: correction_type 'mcp_wrong' renders as 'MCP' badge
      PATH: column cell renderer checks correction_type -> Badge renders label
      CHECK: Text "MCP" present in DOM
      MUTATION: Always rendering "LLM" would fail this test
      ESCAPE: Nothing reasonable -- specific text for specific type
      IMPACT: Users couldn't distinguish correction types visually
    */

    it('renders dash when diff_summary is null', () => {
      const correction = makeCorrection({ diff_summary: null })
      mockUseListPage.mockReturnValue(makeUseListPageReturn([correction]))

      renderCorrectionsPage()

      expect(screen.getByText('--')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders dash when diff_summary is null
      CLAIM: Null diff_summary renders as '--' placeholder
      PATH: column cell renderer checks diff_summary -> renders '--' if null
      CHECK: Text "--" present in DOM
      MUTATION: Rendering empty string or 'null' would fail
      ESCAPE: Nothing reasonable -- exact text match
      IMPACT: Null values would render as blank or "null" string
    */
  })

  describe('filter bars', () => {
    it('renders correction_type filter chips', () => {
      const mockSetFilters = vi.fn()
      mockUseListPage.mockReturnValue(
        makeUseListPageReturn([], { setFilters: mockSetFilters, filters: {} })
      )

      renderCorrectionsPage()

      // Correction type filter options
      expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'LLM Wrong' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'MCP Wrong' })).toBeInTheDocument()
    })

    /*
    ESCAPE: renders correction_type filter chips
      CLAIM: Three filter chip buttons render for correction type
      PATH: CorrectionsPage -> FilterBar(type='chips', options=[All, LLM Wrong, MCP Wrong])
      CHECK: All three buttons exist by role and name
      MUTATION: Missing any option would fail getByRole
      ESCAPE: Nothing reasonable -- all three options verified by exact label
      IMPACT: Users couldn't filter by correction type
    */

    it('renders period filter chips', () => {
      mockUseListPage.mockReturnValue(makeUseListPageReturn([]))

      renderCorrectionsPage()

      expect(screen.getByRole('button', { name: '7 days' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '30 days' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'All time' })).toBeInTheDocument()
    })

    /*
    ESCAPE: renders period filter chips
      CLAIM: Three period filter chip buttons render
      PATH: CorrectionsPage -> FilterBar(type='chips', options=[7 days, 30 days, All time])
      CHECK: All three buttons exist by role and name
      MUTATION: Missing any option would fail getByRole
      ESCAPE: Nothing reasonable -- all three options verified by exact label
      IMPACT: Users couldn't filter by time period
    */

    it('clicking correction_type filter calls setFilters with correction_type', async () => {
      const mockSetFilters = vi.fn()
      mockUseListPage.mockReturnValue(
        makeUseListPageReturn([], { setFilters: mockSetFilters, filters: {} })
      )

      renderCorrectionsPage()

      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: 'LLM Wrong' }))

      expect(mockSetFilters).toHaveBeenCalledTimes(1)
      // Should set correction_type filter while preserving existing period filter
      const callArg = mockSetFilters.mock.calls[0][0]
      expect(callArg.correction_type).toBe('llm_wrong')
    })

    /*
    ESCAPE: clicking correction_type filter calls setFilters with correction_type
      CLAIM: Clicking "LLM Wrong" calls setFilters with correction_type='llm_wrong'
      PATH: FilterBar onClick -> setFilters({correction_type: 'llm_wrong', ...})
      CHECK: setFilters called once; call arg has correction_type === 'llm_wrong'
      MUTATION: Wrong filter key or value would fail; not calling setFilters would fail
      ESCAPE: Other filter keys in the call arg aren't checked, but correction_type is the one under test
      IMPACT: Filter clicks wouldn't update query params
    */

    it('clicking period filter calls setFilters with period', async () => {
      const mockSetFilters = vi.fn()
      mockUseListPage.mockReturnValue(
        makeUseListPageReturn([], { setFilters: mockSetFilters, filters: {} })
      )

      renderCorrectionsPage()

      const user = userEvent.setup()
      await user.click(screen.getByRole('button', { name: '30 days' }))

      expect(mockSetFilters).toHaveBeenCalledTimes(1)
      const callArg = mockSetFilters.mock.calls[0][0]
      expect(callArg.period).toBe('30d')
    })

    /*
    ESCAPE: clicking period filter calls setFilters with period
      CLAIM: Clicking "30 days" calls setFilters with period='30d'
      PATH: FilterBar onClick -> setFilters({period: '30d', ...})
      CHECK: setFilters called once; call arg has period === '30d'
      MUTATION: Wrong period value or key would fail
      ESCAPE: Nothing reasonable -- exact value check
      IMPACT: Period filter wouldn't update query params
    */
  })

  describe('expandable row detail', () => {
    it('shows old_stack and new_stack JSON when row is expanded', async () => {
      const oldEntry = makeStintEntry({ name: 'old-skill', purpose: 'Old purpose' })
      const newEntry = makeStintEntry({ name: 'new-skill', purpose: 'New purpose' })
      const correction = makeCorrection({
        old_stack: [oldEntry],
        new_stack: [newEntry],
      })
      mockUseListPage.mockReturnValue(makeUseListPageReturn([correction]))

      renderCorrectionsPage()

      const user = userEvent.setup()

      // Before expand: detail not visible
      expect(screen.queryByText('Old Stack')).not.toBeInTheDocument()
      expect(screen.queryByText('New Stack')).not.toBeInTheDocument()

      // Click the expand button
      const expandBtn = screen.getByRole('button', { name: /expand/i })
      await user.click(expandBtn)

      // After expand: old_stack and new_stack JSON visible
      expect(screen.getByText('Old Stack')).toBeInTheDocument()
      expect(screen.getByText('New Stack')).toBeInTheDocument()

      // Verify the JSON content includes the stint entry names
      // The structure is: <div><div>Old Stack</div><pre>...</pre></div>
      // So we find the label's parent container div and look for pre within it
      const oldLabel = screen.getByText('Old Stack')
      const oldContainer = oldLabel.parentElement!
      const oldPre = oldContainer.querySelector('pre')
      expect(oldPre).toBeInTheDocument()
      expect(oldPre!.textContent).toBe(JSON.stringify([oldEntry], null, 2))

      const newLabel = screen.getByText('New Stack')
      const newContainer = newLabel.parentElement!
      const newPre = newContainer.querySelector('pre')
      expect(newPre).toBeInTheDocument()
      expect(newPre!.textContent).toBe(JSON.stringify([newEntry], null, 2))
    })

    /*
    ESCAPE: shows old_stack and new_stack JSON when row is expanded
      CLAIM: Expanding a row reveals old_stack and new_stack JSON diff panels
      PATH: Click expand button -> state toggle -> detail row renders
      CHECK: "Old Stack" and "New Stack" labels appear; pre elements contain exact JSON.stringify output
      MUTATION: Not rendering JSON would fail pre content check; wrong JSON.stringify args would produce different output
      ESCAPE: If JSON.stringify produced same output with different args by coincidence. Very unlikely given the indent=2.
      IMPACT: Users couldn't inspect the actual stack changes
    */

    it('collapses detail when expand button is clicked again', async () => {
      const correction = makeCorrection()
      mockUseListPage.mockReturnValue(makeUseListPageReturn([correction]))

      renderCorrectionsPage()

      const user = userEvent.setup()
      const expandBtn = screen.getByRole('button', { name: /expand/i })

      // Expand
      await user.click(expandBtn)
      expect(screen.getByText('Old Stack')).toBeInTheDocument()

      // Collapse -- there are two collapse buttons (table cell + detail panel)
      // Click the first one (the table cell button)
      const collapseButtons = screen.getAllByRole('button', { name: /collapse/i })
      await user.click(collapseButtons[0])
      expect(screen.queryByText('Old Stack')).not.toBeInTheDocument()
    })

    /*
    ESCAPE: collapses detail when expand button is clicked again
      CLAIM: Clicking expand button again collapses the detail row
      PATH: Click expand -> detail visible -> click collapse -> detail hidden
      CHECK: "Old Stack" disappears from DOM after second click
      MUTATION: If toggle didn't work, detail would stay visible
      ESCAPE: Nothing reasonable -- presence then absence verified
      IMPACT: Users couldn't dismiss expanded details
    */
  })
})
