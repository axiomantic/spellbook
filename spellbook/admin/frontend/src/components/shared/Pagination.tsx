import { useState } from 'react'

interface PaginationProps {
  page: number
  pages: number
  total: number
  onPageChange: (page: number) => void
  perPage?: number
  onPerPageChange?: (perPage: number) => void
  showPageSize?: boolean
  showJumpToPage?: boolean
  showTotal?: boolean
  pageSizeOptions?: number[]
  compact?: boolean
}

function getPageNumbers(page: number, pages: number): (number | 'ellipsis')[] {
  if (pages <= 5) {
    return Array.from({ length: pages }, (_, i) => i + 1)
  }

  const result: (number | 'ellipsis')[] = []

  // Always include first page
  result.push(1)

  const neighborStart = Math.max(2, page - 1)
  const neighborEnd = Math.min(pages - 1, page + 1)

  // Leading ellipsis if gap between first page and neighbor window
  if (neighborStart > 2) {
    result.push('ellipsis')
  }

  // Neighbor window (current +/- 1)
  for (let i = neighborStart; i <= neighborEnd; i++) {
    result.push(i)
  }

  // Trailing ellipsis if gap between neighbor window and last page
  if (neighborEnd < pages - 1) {
    result.push('ellipsis')
  }

  // Always include last page
  result.push(pages)

  return result
}

export function Pagination({
  page,
  pages,
  total,
  onPageChange,
  perPage,
  onPerPageChange,
  showPageSize = false,
  showJumpToPage = false,
  showTotal = false,
  pageSizeOptions = [25, 50, 100],
  compact,
}: PaginationProps) {
  const [jumpValue, setJumpValue] = useState('')

  // Default to compact when new props are not used (backward compatible)
  const isCompact = compact !== undefined ? compact : compact === undefined && !showPageSize && !showJumpToPage && !showTotal

  if (isCompact) {
    return (
      <div className="flex items-center justify-between py-3">
        <span className="font-mono text-xs text-text-secondary">
          {total} items / page {page} of {pages}
        </span>
        <div className="flex gap-1">
          <button
            className="btn"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Prev
          </button>
          <button
            className="btn"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    )
  }

  const pageNumbers = pages > 1 ? getPageNumbers(page, pages) : []

  const handleJump = () => {
    const parsed = parseInt(jumpValue, 10)
    if (!isNaN(parsed)) {
      const clamped = Math.max(1, Math.min(pages, parsed))
      onPageChange(clamped)
    }
    setJumpValue('')
  }

  return (
    <div className="flex items-center justify-between py-3 font-mono text-xs">
      <div className="flex items-center gap-3">
        {showTotal && (
          <span className="text-text-secondary">{total} items</span>
        )}

        {showPageSize && onPerPageChange && (
          <div className="flex items-center gap-1" data-testid="page-size-selector">
            {pageSizeOptions.map((size) => (
              <button
                key={size}
                className={`btn px-2 py-0.5 border ${
                  perPage === size ? 'text-accent-green border-accent-green' : 'border-bg-border'
                }`}
                onClick={() => onPerPageChange(size)}
              >
                {size}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        {showJumpToPage && (
          <div className="flex items-center gap-1">
            <input
              type="number"
              aria-label="Go to page"
              className="w-12 bg-transparent border border-bg-border rounded px-1 py-0.5 text-center text-xs font-mono"
              min={1}
              max={pages}
              value={jumpValue}
              onChange={(e) => setJumpValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleJump()
                }
              }}
            />
          </div>
        )}

        <div className="flex gap-1">
          <button
            className="btn"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Prev
          </button>

          {pageNumbers.map((item, idx) =>
            item === 'ellipsis' ? (
              <span
                key={`ellipsis-${idx}`}
                className="px-1 text-text-secondary"
                data-testid="pagination-ellipsis"
              >
                ...
              </span>
            ) : (
              <button
                key={item}
                className={`btn px-2 py-0.5 border ${
                  item === page ? 'text-accent-green border-accent-green' : 'border-bg-border'
                }`}
                onClick={() => onPageChange(item)}
              >
                {item}
              </button>
            )
          )}

          <button
            className="btn"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
