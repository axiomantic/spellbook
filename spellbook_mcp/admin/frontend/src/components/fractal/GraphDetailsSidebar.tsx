import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../shared/Badge'
import { useDeleteGraph, useUpdateGraphStatus } from '../../hooks/useFractalGraph'
import type { CytoscapeResponse } from '../../api/types'

// Must match VALID_TRANSITIONS in spellbook_mcp/fractal/graph_ops.py
/** Valid status transitions for the Change Status dropdown. */
const VALID_TRANSITIONS: Record<string, string[]> = {
  active: ['completed', 'paused', 'error', 'budget_exhausted'],
  paused: ['active'],
  budget_exhausted: ['active', 'completed'],
}

interface GraphDetailsSidebarProps {
  graph: Record<string, unknown>
  stats: CytoscapeResponse['stats'] | null
}

export function GraphDetailsSidebar({ graph, stats }: GraphDetailsSidebarProps) {
  const navigate = useNavigate()
  const deleteGraph = useDeleteGraph()
  const updateStatus = useUpdateGraphStatus()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [seedExpanded, setSeedExpanded] = useState(false)

  const graphId = String(graph.id || '')
  const seed = String(graph.seed || '')
  const status = String(graph.status || '')
  const intensity = String(graph.intensity || '')
  const createdAt = String(graph.created_at || '')
  const updatedAt = String(graph.updated_at || '')

  const transitions = VALID_TRANSITIONS[status] || []
  const isTerminal = transitions.length === 0

  const seedTruncated = seed.length > 120
  const displaySeed = seedExpanded ? seed : seed.slice(0, 120)

  const handleDelete = () => {
    deleteGraph.mutate(graphId, {
      onSuccess: () => {
        navigate('/fractal')
      },
    })
  }

  const handleStatusChange = (newStatus: string) => {
    updateStatus.mutate({ graphId, status: newStatus })
  }

  const formatTimestamp = (ts: string) => {
    if (!ts) return '--'
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim">
        // GRAPH DETAILS
      </h2>

      {/* Seed text */}
      <div>
        <div className="font-mono text-xs text-text-dim mb-1">Seed</div>
        <div className="font-mono text-xs text-text-primary break-words">
          {displaySeed}
          {seedTruncated && !seedExpanded && '...'}
          {seedTruncated && (
            <button
              onClick={() => setSeedExpanded(!seedExpanded)}
              className="ml-1 text-accent-cyan hover:text-accent-green text-xs"
            >
              {seedExpanded ? '[collapse]' : '[expand]'}
            </button>
          )}
        </div>
      </div>

      {/* Status and intensity badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge label={status} />
        <Badge label={intensity} variant="info" />
      </div>

      {/* Timestamps */}
      <div className="space-y-1">
        <div className="font-mono text-xs text-text-dim">
          Created: <span className="text-text-secondary">{formatTimestamp(createdAt)}</span>
        </div>
        <div className="font-mono text-xs text-text-dim">
          Updated: <span className="text-text-secondary">{formatTimestamp(updatedAt)}</span>
        </div>
      </div>

      {/* Node stats */}
      {stats && (
        <div>
          <div className="font-mono text-xs text-text-dim mb-1">Nodes</div>
          <div className="grid grid-cols-2 gap-1">
            <div className="font-mono text-xs text-text-secondary">
              Total: <span className="text-text-primary">{stats.total_nodes}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              Saturated: <span className="text-accent-green">{stats.saturated}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              Pending: <span className="text-accent-amber">{stats.pending}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              Max depth: <span className="text-text-primary">{stats.max_depth}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-1 mt-1">
            <div className="font-mono text-xs text-text-secondary">
              Convergences: <span className="text-accent-cyan">{stats.convergences}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              Contradictions: <span className="text-accent-red">{stats.contradictions}</span>
            </div>
          </div>
        </div>
      )}

      {/* Status change dropdown */}
      {!isTerminal && (
        <div>
          <div className="font-mono text-xs text-text-dim mb-1">Change Status</div>
          <div className="flex flex-wrap gap-1">
            {transitions.map((t) => (
              <button
                key={t}
                onClick={() => handleStatusChange(t)}
                disabled={updateStatus.isPending}
                className="px-2 py-1 border border-bg-border font-mono text-xs text-text-secondary
                           hover:border-accent-cyan hover:text-accent-cyan transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t}
              </button>
            ))}
          </div>
          {updateStatus.isError && (
            <div className="font-mono text-xs text-accent-red mt-1">
              {(updateStatus.error as Error).message}
            </div>
          )}
        </div>
      )}

      {/* Delete button */}
      <div className="pt-2 border-t border-bg-border">
        {!showDeleteConfirm ? (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="w-full px-3 py-2 border border-accent-red text-accent-red font-mono text-xs
                       uppercase tracking-widest hover:bg-accent-red hover:text-bg-base transition-colors"
          >
            Delete Graph
          </button>
        ) : (
          <div className="space-y-2">
            <div className="font-mono text-xs text-accent-red">
              Are you sure? This will permanently delete the graph and all its nodes.
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-3 py-2 border border-bg-border font-mono text-xs
                           text-text-secondary hover:border-text-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteGraph.isPending}
                className="flex-1 px-3 py-2 border border-accent-red bg-accent-red text-bg-base
                           font-mono text-xs uppercase tracking-widest
                           hover:bg-transparent hover:text-accent-red transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteGraph.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
            {deleteGraph.isError && (
              <div className="font-mono text-xs text-accent-red">
                {(deleteGraph.error as Error).message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
