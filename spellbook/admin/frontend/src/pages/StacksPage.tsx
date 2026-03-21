import { useState } from 'react'
import { useStintStacks } from '../hooks/useFocus'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { ErrorDisplay } from '../components/shared/ErrorDisplay'
import { PageLayout } from '../components/layout/PageLayout'
import type { StintStack, StintEntry } from '../api/types'

function shortenPath(path: string): string {
  const segments = path.split('/')
  return segments.length > 2 ? segments.slice(-2).join('/') : path
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function depthColor(depth: number): string {
  if (depth <= 2) return 'bg-accent-green'
  if (depth <= 4) return 'bg-accent-amber'
  return 'bg-accent-red'
}

function depthTextColor(depth: number): string {
  if (depth <= 2) return 'text-accent-green'
  if (depth <= 4) return 'text-accent-amber'
  return 'text-accent-red'
}

function StintRow({ stint }: { stint: StintEntry }) {
  return (
    <tr className="border-b border-bg-border">
      <td className="px-3 py-1.5 font-mono text-xs text-text-primary">{stint.name}</td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-secondary">{stint.behavioral_mode}</td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-dim">{formatTime(stint.entered_at)}</td>
    </tr>
  )
}

function StackCard({ stack }: { stack: StintStack }) {
  const [expanded, setExpanded] = useState(false)
  const topStint = stack.stack[stack.stack.length - 1]
  const maxDepth = 6
  const depthPct = Math.min((stack.depth / maxDepth) * 100, 100)

  return (
    <div className="card mb-4">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="font-mono text-sm text-text-primary truncate">
            {shortenPath(stack.project_path)}
          </span>
          <span className={`font-mono text-xs ${depthTextColor(stack.depth)}`}>
            depth {stack.depth}
          </span>
        </div>
        <span className="font-mono text-xs text-text-dim ml-2 shrink-0">
          {expanded ? '[-]' : '[+]'}
        </span>
      </div>

      {/* Depth gauge */}
      <div className="mt-2 mb-3">
        <div className="w-full bg-bg-surface h-2 border border-bg-border">
          <div
            className={`h-full transition-all ${depthColor(stack.depth)}`}
            style={{ width: `${depthPct}%` }}
          />
        </div>
      </div>

      {/* Top stint summary */}
      {topStint && (
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-xs text-text-primary">{topStint.name}</span>
          {topStint.purpose && (
            <span className="font-mono text-xs text-text-dim truncate">
              &mdash; {topStint.purpose}
            </span>
          )}
        </div>
      )}

      {/* Expanded: full stack */}
      {expanded && stack.stack.length > 0 && (
        <div className="mt-3">
          <table className="w-full text-sm">
            <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border">
              <tr>
                <th className="px-3 py-1.5 text-left">Name</th>
                <th className="px-3 py-1.5 text-left w-32">Mode</th>
                <th className="px-3 py-1.5 text-left w-44">Entered</th>
              </tr>
            </thead>
            <tbody>
              {[...stack.stack].reverse().map((stint, i) => (
                <StintRow key={`${stint.name}-${i}`} stint={stint} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function StacksPage() {
  const { data: stacks, isLoading, error, refetch } = useStintStacks()

  return (
    <PageLayout segments={[{ label: 'ACTIVE STACKS' }]}>
      {isLoading && !stacks && <LoadingSpinner className="py-16" />}

      {error && (
        <ErrorDisplay error={error} title="Failed to load stacks" onRetry={refetch} />
      )}

      {stacks && stacks.length === 0 && (
        <EmptyState
          title="No active stacks"
          message="No sessions currently have an active stint stack."
        />
      )}

      {stacks && stacks.length > 0 && stacks.map((stack) => (
        <StackCard key={stack.project_path} stack={stack} />
      ))}
    </PageLayout>
  )
}
