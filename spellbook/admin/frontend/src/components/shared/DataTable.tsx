import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'
import { Pagination } from './Pagination'
import { LoadingSpinner } from './LoadingSpinner'
import { EmptyState } from './EmptyState'

interface PaginationConfig {
  page: number
  pages: number
  total: number
  perPage: number
  onPageChange: (page: number) => void
  onPerPageChange: (perPage: number) => void
}

interface SortingConfig {
  sortColumn: string | undefined
  sortOrder: 'asc' | 'desc'
  onSortChange: (columnId: string) => void
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface DataTableProps<T> {
  data: T[]
  columns: ColumnDef<T, any>[]
  pagination?: PaginationConfig
  sorting?: SortingConfig
  loading?: boolean
  emptyTitle?: string
  emptyMessage?: string
  onRowClick?: (row: T) => void
  compact?: boolean
}

export function DataTable<T>({
  data,
  columns,
  pagination,
  sorting,
  loading = false,
  emptyTitle = 'No Data',
  emptyMessage,
  onRowClick,
  compact = false,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
  })

  const cellPadding = compact ? 'px-2 py-1' : 'px-3 py-2'
  const headerPadding = compact ? 'px-2 py-1' : 'px-3 py-2'

  return (
    <div className="relative">
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-bg-base/50">
          <LoadingSpinner />
        </div>
      )}

      {!loading && data.length === 0 ? (
        <EmptyState title={emptyTitle} message={emptyMessage} />
      ) : (
        <>
          <div className="overflow-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-bg-border">
                  {table.getHeaderGroups().map((headerGroup) =>
                    headerGroup.headers.map((header) => {
                      const canSort = header.column.getCanSort()
                      const isSorted = sorting && sorting.sortColumn === header.column.id

                      return (
                        <th
                          key={header.id}
                          className={`${headerPadding} text-left select-none ${
                            canSort && sorting
                              ? 'cursor-pointer hover:text-accent-cyan transition-colors'
                              : ''
                          }`}
                          onClick={
                            canSort && sorting
                              ? () => sorting.onSortChange(header.column.id)
                              : undefined
                          }
                        >
                          <span className="font-mono text-xs uppercase tracking-widest text-text-dim">
                            {flexRender(header.column.columnDef.header, header.getContext())}
                          </span>
                          {canSort && isSorted && (
                            <span className="text-accent-cyan font-mono text-xs">
                              {sorting.sortOrder === 'asc' ? ' ^' : ' v'}
                            </span>
                          )}
                        </th>
                      )
                    })
                  )}
                </tr>
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`border-b border-bg-border hover:bg-bg-elevated transition-colors ${
                      onRowClick ? 'cursor-pointer' : ''
                    }`}
                    onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className={`${cellPadding} font-mono text-xs text-text-primary`}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pagination && pagination.pages > 1 && (
            <Pagination
              page={pagination.page}
              pages={pagination.pages}
              total={pagination.total}
              onPageChange={pagination.onPageChange}
            />
          )}
        </>
      )}
    </div>
  )
}
