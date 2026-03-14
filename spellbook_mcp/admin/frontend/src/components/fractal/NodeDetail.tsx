import { Badge } from '../shared/Badge'

interface NodeDetailProps {
  nodeData: Record<string, unknown> | null
  onClose: () => void
}

export function NodeDetail({ nodeData, onClose }: NodeDetailProps) {
  if (!nodeData) return null

  return (
    <div className="absolute right-0 top-0 bottom-0 w-80 bg-bg-surface border-l border-bg-border p-4 overflow-y-auto z-10">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-mono text-xs uppercase tracking-widest text-text-secondary">
          // NODE DETAIL
        </h3>
        <button
          onClick={onClose}
          className="text-text-dim hover:text-text-primary font-mono text-xs"
        >
          [X]
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <div className="font-mono text-xs text-text-dim mb-1">ID</div>
          <div className="font-mono text-sm text-text-primary break-all">
            {String(nodeData.id || '')}
          </div>
        </div>

        <div className="flex gap-2">
          <Badge label={String(nodeData.type || 'unknown')} />
          <Badge label={String(nodeData.status || 'unknown')} />
        </div>

        <div>
          <div className="font-mono text-xs text-text-dim mb-1">DEPTH</div>
          <div className="font-mono text-sm text-text-primary">
            {String(nodeData.depth ?? '-')}
          </div>
        </div>

        {nodeData.owner && (
          <div>
            <div className="font-mono text-xs text-text-dim mb-1">OWNER</div>
            <div className="font-mono text-sm text-text-primary">
              {String(nodeData.owner)}
            </div>
          </div>
        )}

        <div>
          <div className="font-mono text-xs text-text-dim mb-1">CONTENT</div>
          <div className="font-mono text-sm text-text-primary whitespace-pre-wrap bg-bg-primary p-3 border border-bg-border">
            {String(nodeData.label || '')}
          </div>
        </div>

        {nodeData.parent_id && (
          <div>
            <div className="font-mono text-xs text-text-dim mb-1">PARENT</div>
            <div className="font-mono text-sm text-accent-cyan break-all">
              {String(nodeData.parent_id)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
