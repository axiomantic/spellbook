interface PaginationProps {
  page: number
  pages: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pages, total, onPageChange }: PaginationProps) {
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
