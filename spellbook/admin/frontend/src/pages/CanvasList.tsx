import { Link } from 'react-router-dom'
import { useCanvasList } from '../hooks/useCanvases'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { PageLayout } from '../components/layout/PageLayout'
import { Badge } from '../components/shared/Badge'

/**
 * Canvas list page (`/admin/canvas`). Uses the standard list-page layout
 * and UX per OQ-1 (precedent locked in Phase 1.5).
 */
export function CanvasList() {
  const { data, isLoading, isError, error, refetch } = useCanvasList()

  return (
    <PageLayout segments={[{ label: 'CANVAS' }]} fullHeight>
      <div className="p-6">
        <p className="text-sm text-text-secondary mb-4">
          Browse canvases. Each canvas is a single markdown page authored
          by an agent via `canvas_open` / `canvas_write`.
        </p>

        {isError && (
          <div className="border border-accent-red p-4 mb-4">
            <p className="text-accent-red text-sm font-mono mb-2">
              Failed to load canvases:{' '}
              {(error as Error | null)?.message ?? 'unknown error'}
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest hover:bg-accent-green hover:text-bg-base transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {isLoading ? (
          <LoadingSpinner className="py-16" />
        ) : data && data.canvases.length === 0 ? (
          <div className="text-text-dim text-sm font-mono py-16 text-center">
            No canvases yet. Open one with `/canvas open &lt;name&gt;`.
          </div>
        ) : data ? (
          <div className="border border-bg-border">
            <table className="w-full text-sm font-mono">
              <thead className="bg-bg-elevated border-b border-bg-border">
                <tr>
                  <th className="text-left px-3 py-2 text-text-dim uppercase tracking-widest text-xs">
                    Name
                  </th>
                  <th className="text-left px-3 py-2 text-text-dim uppercase tracking-widest text-xs">
                    Title
                  </th>
                  <th className="text-left px-3 py-2 text-text-dim uppercase tracking-widest text-xs">
                    Last Updated
                  </th>
                  <th className="text-left px-3 py-2 text-text-dim uppercase tracking-widest text-xs">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.canvases.map((c) => (
                  <tr
                    key={c.name}
                    className="border-b border-bg-border hover:bg-bg-elevated"
                  >
                    <td className="px-3 py-2">
                      <Link
                        to={`/canvas/${c.name}`}
                        className="text-accent-cyan hover:text-accent-green"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-text-primary">{c.title}</td>
                    <td className="px-3 py-2 text-text-dim">
                      {c.last_updated}
                    </td>
                    <td className="px-3 py-2">
                      {c.closed ? (
                        <Badge label="closed" variant="warning" />
                      ) : (
                        <Badge label="open" variant="info" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </PageLayout>
  )
}
