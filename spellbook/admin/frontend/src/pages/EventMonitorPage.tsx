import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { useEventStream } from '../hooks/useEventStream'
import { EmptyState } from '../components/shared/EmptyState'
import { PageLayout } from '../components/layout/PageLayout'
import type { WSEvent } from '../api/types'

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString(undefined, {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ts
  }
}

function SubsystemFilterBar({
  knownSubsystems,
  activeSubsystems,
  onToggle,
}: {
  knownSubsystems: Set<string>
  activeSubsystems: Set<string>
  onToggle: (subsystem: string) => void
}) {
  const sorted = useMemo(
    () => Array.from(knownSubsystems).sort(),
    [knownSubsystems],
  )

  if (sorted.length === 0) return null

  return (
    <div className="flex gap-1 flex-wrap">
      {sorted.map((sub) => {
        const isActive = activeSubsystems.size === 0 || activeSubsystems.has(sub)
        return (
          <button
            key={sub}
            onClick={() => onToggle(sub)}
            className={`px-2 py-1 font-mono text-xs uppercase tracking-widest transition-colors border ${
              isActive
                ? 'text-accent-green border-accent-green bg-bg-elevated'
                : 'text-text-dim border-bg-border hover:text-text-secondary'
            }`}
          >
            {sub}
          </button>
        )
      })}
    </div>
  )
}

function EventRow({
  event,
  isExpanded,
  onClick,
}: {
  event: WSEvent
  isExpanded: boolean
  onClick: () => void
}) {
  return (
    <div
      className="border-b border-bg-border cursor-pointer hover:bg-bg-elevated transition-colors"
      onClick={onClick}
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <span className="font-mono text-xs text-text-dim shrink-0 w-20">
          {formatTimestamp(event.timestamp)}
        </span>
        <span className="font-mono text-xs text-accent-cyan shrink-0 w-24 uppercase">
          {event.subsystem}
        </span>
        <span className="font-mono text-xs text-text-primary truncate flex-1">
          {event.event}
        </span>
      </div>
      {isExpanded && (
        <div className="px-3 pb-3">
          <pre className="font-mono text-xs text-text-secondary bg-bg-elevated border border-bg-border p-2 overflow-auto max-h-64">
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export function EventMonitorPage() {
  const [paused, setPaused] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [activeSubsystems, setActiveSubsystems] = useState<Set<string>>(new Set())
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const subsystemFilter = useMemo(
    () => (activeSubsystems.size > 0 ? activeSubsystems : undefined),
    [activeSubsystems],
  )

  const { events, isConnected, clear, knownSubsystems } = useEventStream({
    subsystemFilter,
    paused,
  })

  const handleToggleSubsystem = useCallback((subsystem: string) => {
    setActiveSubsystems((prev) => {
      const next = new Set(prev)
      if (next.has(subsystem)) {
        next.delete(subsystem)
      } else {
        next.add(subsystem)
      }
      return next
    })
  }, [])

  // Auto-scroll to top when new events arrive (events are newest-first)
  useEffect(() => {
    if (autoScroll && scrollContainerRef.current && events.length > 0) {
      scrollContainerRef.current.scrollTop = 0
    }
  }, [events.length, autoScroll])

  return (
    <PageLayout
      segments={[{ label: 'EVENT MONITOR' }]}
      fullHeight
      headerRight={
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-mono text-xs">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                isConnected ? 'bg-accent-green' : 'bg-accent-red'
              }`}
            />
            <span className={isConnected ? 'text-accent-green' : 'text-accent-red'}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </span>
          <span className="font-mono text-xs text-text-dim">
            {events.length} events
          </span>
        </div>
      }
    >
      <div className="p-6 pb-0">
        {/* Controls */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <SubsystemFilterBar
            knownSubsystems={knownSubsystems}
            activeSubsystems={activeSubsystems}
            onToggle={handleToggleSubsystem}
          />

          <div className="flex gap-2 shrink-0">
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors border ${
                autoScroll
                  ? 'text-accent-green border-accent-green'
                  : 'text-text-secondary border-bg-border'
              }`}
            >
              Auto-scroll
            </button>
            <button
              onClick={() => setPaused(!paused)}
              className={`px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors border ${
                paused
                  ? 'text-accent-amber border-accent-amber'
                  : 'text-text-secondary border-bg-border'
              }`}
            >
              {paused ? 'Paused' : 'Pause'}
            </button>
            <button
              onClick={() => {
                clear()
                setExpandedIndex(null)
              }}
              className="px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-text-secondary border border-bg-border hover:text-accent-cyan transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* Event list */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-auto border-t border-bg-border"
      >
        {events.length === 0 && (
          <EmptyState
            title="No events yet"
            message={
              isConnected
                ? 'Waiting for events from the event bus...'
                : 'WebSocket is not connected.'
            }
          />
        )}

        {events.map((event, index) => (
          <EventRow
            key={`${event.timestamp}-${event.subsystem}-${event.event}-${index}`}
            event={event}
            isExpanded={expandedIndex === index}
            onClick={() =>
              setExpandedIndex(expandedIndex === index ? null : index)
            }
          />
        ))}
      </div>
    </PageLayout>
  )
}
