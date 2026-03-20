import { useState } from 'react'
import { useStintStacks, useCorrectionEvents } from '../hooks/useFocus'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { PageLayout } from '../components/layout/PageLayout'
import type { StintStack, StintEntry, CorrectionEvent } from '../api/types'

const PERIODS = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'all', label: 'All time' },
] as const

const CORRECTION_FILTERS = [
  { value: '', label: 'All' },
  { value: 'llm_wrong', label: 'LLM Wrong' },
  { value: 'mcp_wrong', label: 'MCP Wrong' },
] as const

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

function TypeBadge({ type }: { type: string }) {
  const colorMap: Record<string, string> = {
    skill: 'text-accent-cyan border-accent-cyan',
    subagent: 'text-accent-amber border-accent-amber',
    custom: 'text-accent-purple border-accent-purple',
  }
  const colors = colorMap[type] || 'text-text-secondary border-text-secondary'
  return (
    <span
      className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${colors}`}
    >
      {type}
    </span>
  )
}

function CorrectionTypeBadge({ type }: { type: 'llm_wrong' | 'mcp_wrong' }) {
  const colors =
    type === 'llm_wrong'
      ? 'text-accent-red border-accent-red'
      : 'text-accent-green border-accent-green'
  return (
    <span
      className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${colors}`}
    >
      {type === 'llm_wrong' ? 'LLM' : 'MCP'}
    </span>
  )
}

function StintRow({ stint }: { stint: StintEntry }) {
  return (
    <tr className="border-b border-bg-border">
      <td className="px-3 py-1.5 font-mono text-xs text-text-primary">{stint.name}</td>
      <td className="px-3 py-1.5">
        <TypeBadge type={stint.type} />
      </td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-secondary">{stint.behavioral_mode}</td>
      <td className="px-3 py-1.5 font-mono text-xs text-text-dim">{formatTime(stint.entered_at)}</td>
    </tr>
  )
}

function StackCard({ stack }: { stack: StintStack }) {
  const [expanded, setExpanded] = useState(false)
  const topStint = stack.stack[stack.stack.length - 1]
  const maxDepth = 8
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
          <TypeBadge type={topStint.type} />
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
                <th className="px-3 py-1.5 text-left w-24">Type</th>
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

function CorrectionRow({ event }: { event: CorrectionEvent }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr
        className="border-b border-bg-border hover:bg-bg-elevated transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2 font-mono text-xs text-text-dim">
          {formatTime(event.created_at)}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-text-primary">
          {shortenPath(event.project_path)}
        </td>
        <td className="px-3 py-2">
          <CorrectionTypeBadge type={event.correction_type} />
        </td>
        <td className="px-3 py-2 font-mono text-xs text-text-secondary">
          {event.diff_summary || '--'}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-text-dim">
          {expanded ? '[-]' : '[+]'}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-bg-border">
          <td colSpan={5} className="px-3 py-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="font-mono text-xs uppercase tracking-widest text-text-dim mb-2">
                  Old Stack
                </div>
                <pre className="font-mono text-xs text-text-secondary bg-bg-surface border border-bg-border p-2 overflow-auto max-h-48">
                  {JSON.stringify(event.old_stack, null, 2)}
                </pre>
              </div>
              <div>
                <div className="font-mono text-xs uppercase tracking-widest text-text-dim mb-2">
                  New Stack
                </div>
                <pre className="font-mono text-xs text-text-secondary bg-bg-surface border border-bg-border p-2 overflow-auto max-h-48">
                  {JSON.stringify(event.new_stack, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function FocusPage() {
  const [period, setPeriod] = useState('7d')
  const [correctionType, setCorrectionType] = useState('')

  const { data: stacks, isLoading: stacksLoading } = useStintStacks()
  const { data: corrections, isLoading: correctionsLoading } = useCorrectionEvents({
    period,
    correction_type: correctionType || undefined,
  })

  return (
    <PageLayout segments={[{ label: 'ACTIVE FOCUS STACKS' }]}>
      {/* ACTIVE_FOCUS_STACKS */}
      <div className="mb-8">

        {stacksLoading && !stacks && <LoadingSpinner className="py-16" />}

        {stacks && stacks.length === 0 && (
          <EmptyState
            title="No active focus stacks"
            message="No sessions currently have an active focus context."
          />
        )}

        {stacks && stacks.length > 0 && stacks.map((stack) => (
          <StackCard key={stack.project_path} stack={stack} />
        ))}
      </div>

      {/* CORRECTION_LOG */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-mono text-sm uppercase tracking-widest text-text-secondary">
            // Correction Log
          </h2>
          <div className="flex gap-3">
            {/* Correction type filter */}
            <div className="flex gap-1">
              {CORRECTION_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setCorrectionType(f.value)}
                  className={`px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors border ${
                    correctionType === f.value
                      ? 'text-accent-green border-accent-green bg-bg-elevated'
                      : 'text-text-secondary border-bg-border hover:text-accent-cyan'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            {/* Period selector */}
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPeriod(p.value)}
                  className={`px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors border ${
                    period === p.value
                      ? 'text-accent-green border-accent-green bg-bg-elevated'
                      : 'text-text-secondary border-bg-border hover:text-accent-cyan'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {correctionsLoading && !corrections && <LoadingSpinner className="py-16" />}

        {corrections && corrections.length === 0 && (
          <EmptyState
            title="No correction events"
            message="No focus corrections recorded for the selected filters."
          />
        )}

        {corrections && corrections.length > 0 && (
          <div className="card">
            <table className="w-full text-sm">
              <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border">
                <tr>
                  <th className="px-3 py-2 text-left w-44">Timestamp</th>
                  <th className="px-3 py-2 text-left">Project</th>
                  <th className="px-3 py-2 text-left w-24">Type</th>
                  <th className="px-3 py-2 text-left">Diff Summary</th>
                  <th className="px-3 py-2 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {corrections.map((event) => (
                  <CorrectionRow key={event.id} event={event} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
