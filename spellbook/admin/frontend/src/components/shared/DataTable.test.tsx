import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { createColumnHelper } from '@tanstack/react-table'
import { DataTable } from './DataTable'

// --- Test data types and helpers ---

interface TestRow {
  id: number
  name: string
  status: string
}

const columnHelper = createColumnHelper<TestRow>()

const sortableColumns = [
  columnHelper.accessor('name', {
    header: 'Name',
    enableSorting: true,
  }),
  columnHelper.accessor('status', {
    header: 'Status',
    enableSorting: false,
  }),
]

const testData: TestRow[] = [
  { id: 1, name: 'Alice', status: 'active' },
  { id: 2, name: 'Bob', status: 'inactive' },
]

const defaultPagination = {
  page: 1,
  pages: 3,
  total: 25,
  perPage: 10,
  onPageChange: vi.fn(),
  onPerPageChange: vi.fn(),
}

// --- Tests ---

describe('DataTable', () => {
  describe('header rendering', () => {
    it('renders column headers from column definitions', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const thead = container.querySelector('thead')!
      expect(thead).toBeInTheDocument()

      const headerCells = thead.querySelectorAll('th')
      expect(headerCells.length).toBe(2)
      expect(headerCells[0].textContent).toBe('Name')
      expect(headerCells[1].textContent).toBe('Status')
    })
  })

  describe('data row rendering', () => {
    it('renders rows with cell content from data', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      expect(rows.length).toBe(2)

      // First row
      const row1Cells = rows[0].querySelectorAll('td')
      expect(row1Cells[0].textContent).toBe('Alice')
      expect(row1Cells[1].textContent).toBe('active')

      // Second row
      const row2Cells = rows[1].querySelectorAll('td')
      expect(row2Cells[0].textContent).toBe('Bob')
      expect(row2Cells[1].textContent).toBe('inactive')
    })
  })

  describe('sort indicators', () => {
    it('shows ^ indicator with accent-cyan for ascending sort on active column', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          sorting={{
            sortColumn: 'name',
            sortOrder: 'asc',
            onSortChange: vi.fn(),
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const nameHeader = thead.querySelectorAll('th')[0]
      // Should contain ^ indicator
      expect(nameHeader.textContent).toBe('Name ^')
      // The sort indicator span should have accent-cyan styling
      const indicatorSpan = nameHeader.querySelector('.text-accent-cyan')
      expect(indicatorSpan).toBeInTheDocument()
      expect(indicatorSpan!.textContent).toBe(' ^')
    })

    it('shows v indicator with accent-cyan for descending sort on active column', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          sorting={{
            sortColumn: 'name',
            sortOrder: 'desc',
            onSortChange: vi.fn(),
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const nameHeader = thead.querySelectorAll('th')[0]
      expect(nameHeader.textContent).toBe('Name v')
      const indicatorSpan = nameHeader.querySelector('.text-accent-cyan')
      expect(indicatorSpan).toBeInTheDocument()
      expect(indicatorSpan!.textContent).toBe(' v')
    })

    it('shows no indicator on unsorted columns', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          sorting={{
            sortColumn: 'name',
            sortOrder: 'asc',
            onSortChange: vi.fn(),
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const statusHeader = thead.querySelectorAll('th')[1]
      // Status column has enableSorting: false, so no indicator at all
      expect(statusHeader.textContent).toBe('Status')
      expect(statusHeader.querySelector('.text-accent-cyan')).toBeNull()
    })

    it('shows no indicator on sortable column that is not currently sorted', () => {
      const columns = [
        columnHelper.accessor('name', { header: 'Name', enableSorting: true }),
        columnHelper.accessor('status', { header: 'Status', enableSorting: true }),
      ]

      const { container } = render(
        <DataTable
          data={testData}
          columns={columns}
          sorting={{
            sortColumn: 'name',
            sortOrder: 'asc',
            onSortChange: vi.fn(),
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const statusHeader = thead.querySelectorAll('th')[1]
      // Status is sortable but not active, so no indicator
      expect(statusHeader.textContent).toBe('Status')
      expect(statusHeader.querySelector('.text-accent-cyan')).toBeNull()
    })
  })

  describe('sort clickability', () => {
    it('sortable column header has cursor-pointer and calls onSortChange on click', async () => {
      const user = userEvent.setup()
      const onSortChange = vi.fn()

      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          sorting={{
            sortColumn: undefined,
            sortOrder: 'asc',
            onSortChange,
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const nameHeader = thead.querySelectorAll('th')[0]
      expect(nameHeader.className).toContain('cursor-pointer')

      await user.click(nameHeader)
      expect(onSortChange).toHaveBeenCalledTimes(1)
      expect(onSortChange).toHaveBeenCalledWith('name')
    })

    it('non-sortable column header does NOT have cursor-pointer and does not call onSortChange', async () => {
      const user = userEvent.setup()
      const onSortChange = vi.fn()

      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          sorting={{
            sortColumn: undefined,
            sortOrder: 'asc',
            onSortChange,
          }}
        />
      )

      const thead = container.querySelector('thead')!
      const statusHeader = thead.querySelectorAll('th')[1]
      expect(statusHeader.className).not.toContain('cursor-pointer')

      await user.click(statusHeader)
      expect(onSortChange).not.toHaveBeenCalled()
    })
  })

  describe('loading state', () => {
    it('renders LoadingSpinner overlay when loading is true', () => {
      const { container } = render(
        <DataTable
          data={[]}
          columns={sortableColumns}
          loading={true}
        />
      )

      // LoadingSpinner renders an animated spinner
      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })

    it('does not render LoadingSpinner when loading is false', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          loading={false}
        />
      )

      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeNull()
    })
  })

  describe('empty state', () => {
    it('renders EmptyState component when data is empty and not loading', () => {
      render(
        <DataTable
          data={[]}
          columns={sortableColumns}
          loading={false}
        />
      )

      // EmptyState renders "No Data" title by default
      expect(screen.getByText('No Data')).toBeInTheDocument()
    })

    it('renders custom empty title and message', () => {
      render(
        <DataTable
          data={[]}
          columns={sortableColumns}
          loading={false}
          emptyTitle="No Results"
          emptyMessage="Try adjusting your filters."
        />
      )

      expect(screen.getByText('No Results')).toBeInTheDocument()
      expect(screen.getByText('Try adjusting your filters.')).toBeInTheDocument()
    })

    it('does not render EmptyState when data has rows', () => {
      render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          loading={false}
        />
      )

      expect(screen.queryByText('No Data')).not.toBeInTheDocument()
    })
  })

  describe('row interaction', () => {
    it('calls onRowClick with row data when a row is clicked', async () => {
      const user = userEvent.setup()
      const onRowClick = vi.fn()

      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          onRowClick={onRowClick}
        />
      )

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      await user.click(rows[0])

      expect(onRowClick).toHaveBeenCalledTimes(1)
      expect(onRowClick).toHaveBeenCalledWith(testData[0])
    })

    it('rows have cursor-pointer when onRowClick is provided', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          onRowClick={vi.fn()}
        />
      )

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      expect(rows[0].className).toContain('cursor-pointer')
    })

    it('rows do NOT have cursor-pointer when onRowClick is not provided', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      expect(rows[0].className).not.toContain('cursor-pointer')
    })
  })

  describe('pagination footer', () => {
    it('renders Pagination component when pagination prop is provided', () => {
      render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          pagination={defaultPagination}
        />
      )

      // Pagination component renders "25 items / page 1 of 3"
      expect(screen.getByText('25 items / page 1 of 3')).toBeInTheDocument()
      // Has Prev/Next buttons
      expect(screen.getByText('Prev')).toBeInTheDocument()
      expect(screen.getByText('Next')).toBeInTheDocument()
    })

    it('does not render Pagination when pagination prop is not provided', () => {
      render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      expect(screen.queryByText('Prev')).not.toBeInTheDocument()
      expect(screen.queryByText('Next')).not.toBeInTheDocument()
    })

    it('calls onPageChange when Next is clicked', async () => {
      const user = userEvent.setup()
      const onPageChange = vi.fn()

      render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          pagination={{ ...defaultPagination, onPageChange }}
        />
      )

      await user.click(screen.getByText('Next'))
      expect(onPageChange).toHaveBeenCalledTimes(1)
      expect(onPageChange).toHaveBeenCalledWith(2)
    })
  })

  describe('compact mode', () => {
    it('applies tighter padding in compact mode', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          compact={true}
        />
      )

      const tbody = container.querySelector('tbody')!
      const firstCell = tbody.querySelector('td')!
      // Compact mode uses px-2 py-1 instead of px-3 py-2
      expect(firstCell.className).toContain('px-2')
      expect(firstCell.className).toContain('py-1')
      expect(firstCell.className).not.toContain('px-3')
      expect(firstCell.className).not.toContain('py-2')
    })

    it('applies standard padding when compact is false', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
          compact={false}
        />
      )

      const tbody = container.querySelector('tbody')!
      const firstCell = tbody.querySelector('td')!
      expect(firstCell.className).toContain('px-3')
      expect(firstCell.className).toContain('py-2')
    })
  })

  describe('styling conventions', () => {
    it('uses font-mono text-xs on table cells', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const tbody = container.querySelector('tbody')!
      const firstCell = tbody.querySelector('td')!
      expect(firstCell.className).toContain('font-mono')
      expect(firstCell.className).toContain('text-xs')
    })

    it('rows have hover:bg-bg-elevated and border-b border-bg-border', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const tbody = container.querySelector('tbody')!
      const row = tbody.querySelectorAll('tr')[0]
      expect(row.className).toContain('hover:bg-bg-elevated')
      expect(row.className).toContain('border-b')
      expect(row.className).toContain('border-bg-border')
    })

    it('header row has border-b border-bg-border', () => {
      const { container } = render(
        <DataTable
          data={testData}
          columns={sortableColumns}
        />
      )

      const thead = container.querySelector('thead')!
      const headerRow = thead.querySelector('tr')!
      expect(headerRow.className).toContain('border-b')
      expect(headerRow.className).toContain('border-bg-border')
    })
  })
})
