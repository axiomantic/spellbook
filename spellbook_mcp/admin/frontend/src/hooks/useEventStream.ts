import { useState, useCallback, useEffect, useRef } from 'react'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import { fetchApi } from '../api/client'
import type { WSEvent } from '../api/types'

const MAX_EVENTS = 200

interface RecentEventsResponse {
  events: WSEvent[]
  total: number
}

interface UseEventStreamOptions {
  /** Subsystems to include (empty = all). */
  subsystemFilter?: Set<string>
  /** Whether event capture is paused. */
  paused?: boolean
}

interface UseEventStreamResult {
  /** Captured events (newest first). */
  events: WSEvent[]
  /** Whether the WebSocket is connected. */
  isConnected: boolean
  /** Clear all captured events. */
  clear: () => void
  /** Set of all subsystems seen so far. */
  knownSubsystems: Set<string>
  /** Whether historical events are still loading. */
  isLoadingHistory: boolean
}

export function useEventStream({
  subsystemFilter,
  paused = false,
}: UseEventStreamOptions = {}): UseEventStreamResult {
  const { events: wsEvents, isConnected } = useWebSocketContext()
  const [captured, setCaptured] = useState<WSEvent[]>([])
  const [knownSubsystems, setKnownSubsystems] = useState<Set<string>>(new Set())
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const prevLengthRef = useRef(0)
  const pausedRef = useRef(paused)
  const historyLoadedRef = useRef(false)

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  // Load historical events on mount
  useEffect(() => {
    if (historyLoadedRef.current) return
    historyLoadedRef.current = true

    fetchApi<RecentEventsResponse>('/api/events/recent', {
      params: { limit: 100, since_hours: 24 },
    })
      .then((resp) => {
        if (resp.events.length > 0) {
          setCaptured((prev) => [...prev, ...resp.events].slice(0, MAX_EVENTS))
          setKnownSubsystems((prev) => {
            const next = new Set(prev)
            for (const ev of resp.events) {
              next.add(ev.subsystem)
            }
            return next
          })
        }
      })
      .catch(() => {
        // Silently ignore -- historical events are best-effort
      })
      .finally(() => {
        setIsLoadingHistory(false)
      })
  }, [])

  // Watch for new events from the WebSocket context
  useEffect(() => {
    // wsEvents is newest-first; detect new events by comparing length
    const newCount = wsEvents.length - prevLengthRef.current
    if (newCount <= 0 && wsEvents.length !== 0) {
      // Context buffer may have been reset or no new events
      prevLengthRef.current = wsEvents.length
      return
    }

    // Take the newest events that we haven't seen
    const incoming = newCount > 0 ? wsEvents.slice(0, newCount) : wsEvents

    if (incoming.length === 0) {
      prevLengthRef.current = wsEvents.length
      return
    }

    // Track known subsystems
    setKnownSubsystems((prev) => {
      const next = new Set(prev)
      let changed = false
      for (const ev of incoming) {
        if (!next.has(ev.subsystem)) {
          next.add(ev.subsystem)
          changed = true
        }
      }
      return changed ? next : prev
    })

    if (!pausedRef.current) {
      setCaptured((prev) => {
        // Filter by subsystem if filter is active
        const filtered =
          subsystemFilter && subsystemFilter.size > 0
            ? incoming.filter((ev) => subsystemFilter.has(ev.subsystem))
            : incoming
        if (filtered.length === 0) return prev
        return [...filtered, ...prev].slice(0, MAX_EVENTS)
      })
    }

    prevLengthRef.current = wsEvents.length
  }, [wsEvents, subsystemFilter])

  const clear = useCallback(() => {
    setCaptured([])
  }, [])

  return { events: captured, isConnected, clear, knownSubsystems, isLoadingHistory }
}
