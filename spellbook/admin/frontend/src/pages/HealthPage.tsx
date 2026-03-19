import { useHealthMatrix } from '../hooks/useHealth'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import type { SubsystemHealth, TableHealth } from '../api/types'

const STATUS_COLORS: Record<string, string> = {
  healthy: 'text-accent-green border-accent-green',
  idle: 'text-accent-amber border-accent-amber',
  error: 'text-accent-red border-accent-red',
  missing: 'text-text-dim border-text-dim',
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(ts: string | null): string {
  if (!ts) return '--'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] || 'text-text-secondary border-text-secondary'
  return (
    <span
      className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${colors}`}
    >
      {status}
    </span>
  )
}

function TableRow({ table }: { table: TableHealth }) {
  return (
    <tr className="border-b border-bg-border hover:bg-bg-elevated transition-colors">
      <td className="px-3 py-1.5 font-mono text-xs text-text-secondary pl-8">
        {table.name}
      </td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-secondary text-right">
        {table.row_count >= 0 ? table.row_count.toLocaleString() : 'err'}
      </td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-dim">
        {formatTime(table.last_activity)}
      </td>
    </tr>
  )
}

function DatabaseCard({ db }: { db: SubsystemHealth }) {
  return (
    <div className="card mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-text-primary">{db.name}</span>
          <StatusBadge status={db.status} />
        </div>
        <span className="font-mono text-xs text-text-dim">
          {formatSize(db.size_bytes)}
        </span>
      </div>

      {db.tables.length > 0 && (
        <table className="w-full text-sm">
          <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border">
            <tr>
              <th className="px-3 py-1.5 text-left pl-8">Table</th>
              <th className="px-3 py-1.5 text-right w-28">Rows</th>
              <th className="px-3 py-1.5 text-left w-48">Last Activity</th>
            </tr>
          </thead>
          <tbody>
            {db.tables.map((table) => (
              <TableRow key={table.name} table={table} />
            ))}
          </tbody>
        </table>
      )}

      {db.tables.length === 0 && db.status === 'missing' && (
        <p className="font-mono text-xs text-text-dim pl-2">Database file not found.</p>
      )}
    </div>
  )
}

export function HealthPage() {
  const { data, isLoading, isError } = useHealthMatrix()

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-mono text-sm uppercase tracking-widest text-text-secondary">
          // Health Matrix
        </h1>
        {data && (
          <span className="font-mono text-xs text-text-dim">
            Updated: {formatTime(data.generated_at)}
          </span>
        )}
      </div>

      {isLoading && <LoadingSpinner className="py-16" />}
      {isError && (
        <EmptyState
          title="Error loading health data"
          message="Failed to fetch subsystem health matrix."
        />
      )}

      {data &&
        data.databases.map((db) => <DatabaseCard key={db.name} db={db} />)}
    </div>
  )
}
