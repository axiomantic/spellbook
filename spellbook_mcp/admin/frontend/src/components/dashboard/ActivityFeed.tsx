import { useRef } from 'react'
import { Badge } from '../shared/Badge'
import { useWebSocketContext } from '../../contexts/WebSocketContext'
import type { WSEvent } from '../../api/types'

interface ActivityFeedProps {
  /** Initial items from the dashboard API (polled activity). */
  initialItems?: Array<{ type: string; timestamp: string; summary: string }>
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    return date.toLocaleDateString()
  } catch {
    return ts
  }
}

interface FeedItem {
  type: string
  timestamp: string
  summary: string
  live?: boolean
}

const MAX_ITEMS = 50

export function ActivityFeed({ initialItems = [] }: ActivityFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { events } = useWebSocketContext()

  // Convert live WebSocket events to feed items
  const liveItems: FeedItem[] = events.map((event) => ({
    type: `${event.subsystem}.${event.event}`,
    timestamp: event.timestamp,
    summary: summarizeEvent(event),
    live: true,
  }))

  const allItems = [...liveItems, ...initialItems.map((i) => ({ ...i, live: false }))]
    .slice(0, MAX_ITEMS)

  return (
    <div ref={containerRef} className="max-h-96 overflow-y-auto">
      {allItems.length === 0 ? (
        <p className="text-text-dim text-sm font-mono">No recent activity.</p>
      ) : (
        allItems.map((item, i) => (
          <div
            key={`${item.timestamp}-${i}`}
            className={`flex items-start gap-3 py-2 border-b border-bg-border last:border-b-0 ${
              item.live ? 'animate-pulse' : ''
            }`}
          >
            <Badge label={item.type} />
            <span className="text-text-primary text-sm font-mono flex-1 truncate">
              {item.summary}
            </span>
            <span className="text-text-dim text-xs font-mono whitespace-nowrap">
              {formatTimestamp(item.timestamp)}
            </span>
          </div>
        ))
      )}
    </div>
  )
}

function summarizeEvent(event: WSEvent): string {
  const data = event.data
  switch (event.subsystem) {
    case 'memory':
      if (event.event === 'memory.created') return `${data.count || 1} memories stored`
      if (event.event === 'memory.deleted') return `Memory ${(data.memory_id as string)?.slice(0, 8) || ''} deleted`
      if (event.event === 'memory.updated') return `Memory ${(data.memory_id as string)?.slice(0, 8) || ''} updated`
      return event.event
    case 'config':
      return `Config "${data.key || ''}" updated`
    case 'security':
      return `Security: ${data.event_type || event.event}`
    default:
      return event.event
  }
}
