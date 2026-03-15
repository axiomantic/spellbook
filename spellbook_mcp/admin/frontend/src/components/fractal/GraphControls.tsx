interface GraphControlsProps {
  maxDepth: number | undefined
  onMaxDepthChange: (depth: number | undefined) => void
  stats?: {
    total_nodes: number
    saturated: number
    pending: number
    max_depth: number
    convergences: number
    contradictions: number
  }
  graphMaxDepth?: number
}

export function GraphControls({ maxDepth, onMaxDepthChange, stats, graphMaxDepth: graphMaxDepthProp }: GraphControlsProps) {
  const graphMaxDepth = graphMaxDepthProp ?? stats?.max_depth ?? 10

  return (
    <div className="bg-bg-surface border border-bg-border p-3 space-y-3">
      {/* Depth Filter */}
      <div>
        <label className="font-mono text-xs text-text-dim uppercase tracking-widest block mb-1">
          // DEPTH FILTER
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={graphMaxDepth}
            value={maxDepth ?? graphMaxDepth}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10)
              onMaxDepthChange(val >= graphMaxDepth ? undefined : val)
            }}
            className="flex-1 accent-accent-green"
          />
          <span className="font-mono text-xs text-text-primary w-12 text-right">
            {maxDepth ?? 'ALL'}
          </span>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center">
            <div className="font-mono text-lg text-text-primary">{stats.total_nodes}</div>
            <div className="font-mono text-xs text-text-dim">NODES</div>
          </div>
          <div className="text-center">
            <div className="font-mono text-lg text-accent-green">{stats.saturated}</div>
            <div className="font-mono text-xs text-text-dim">DONE</div>
          </div>
          <div className="text-center">
            <div className="font-mono text-lg text-accent-amber">{stats.pending}</div>
            <div className="font-mono text-xs text-text-dim">OPEN</div>
          </div>
        </div>
      )}

      {stats && (stats.convergences > 0 || stats.contradictions > 0) && (
        <div className="flex gap-4 text-xs font-mono">
          {stats.convergences > 0 && (
            <span className="text-accent-cyan">{stats.convergences} convergences</span>
          )}
          {stats.contradictions > 0 && (
            <span className="text-accent-red">{stats.contradictions} contradictions</span>
          )}
        </div>
      )}
    </div>
  )
}
