import { Badge } from '../shared/Badge'
import type { FractalGraphSummary } from '../../api/types'

interface GraphListProps {
  graphs: FractalGraphSummary[]
  selectedId: string | null
  onSelect: (graphId: string) => void
}

export function GraphList({ graphs, selectedId, onSelect }: GraphListProps) {
  return (
    <div className="space-y-1">
      {graphs.map((g) => (
        <button
          key={g.id}
          onClick={() => onSelect(g.id)}
          className={`w-full text-left px-3 py-2 border transition-colors ${
            selectedId === g.id
              ? 'border-accent-green bg-bg-elevated'
              : 'border-bg-border bg-bg-surface hover:border-accent-cyan'
          }`}
        >
          <div className="font-mono text-xs text-text-primary truncate">
            {g.seed}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <Badge label={g.status} />
            <span className="font-mono text-xs text-text-dim">
              {g.total_nodes} nodes
            </span>
          </div>
        </button>
      ))}
    </div>
  )
}
