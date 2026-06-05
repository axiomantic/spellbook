import { useEffect, useRef, useCallback, useState } from 'react'
import { fetchApi } from '../api/client'
import type { WSEvent, WSControl } from '../api/types'

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketOptions {
  onEvent?: (event: WSEvent) => void
  /**
   * Fired when a connection opens that is NOT the first one — i.e. a
   * reconnect after a drop (design D2). Lets the consumer resync state that
   * may have changed while the socket was down (e.g. invalidate the canvas
   * query so a tab offline during a decision event catches up). The very first
   * connect is intentionally skipped: the initial data load is the query's own
   * responsibility, and invalidating on mount would force a redundant refetch.
   */
  onReconnect?: () => void
  enabled?: boolean
}

const MAX_BACKOFF = 30_000
const INITIAL_BACKOFF = 1_000

export function useWebSocket({ onEvent, onReconnect, enabled = true }: UseWebSocketOptions = {}) {
  const [state, setState] = useState<ConnectionState>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(INITIAL_BACKOFF)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const enabledRef = useRef(enabled)
  const scheduleReconnectRef = useRef<(() => void) | undefined>(undefined)
  // Distinguishes the first successful open (initial load — no resync) from a
  // reconnect open (resync via onReconnect). D2.
  const hasConnectedRef = useRef(false)
  const onReconnectRef = useRef(onReconnect)

  useEffect(() => {
    onReconnectRef.current = onReconnect
  }, [onReconnect])

  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  const connect = useCallback(async () => {
    if (!enabledRef.current) return

    try {
      setState('connecting')
      // Get a WS ticket via the auth endpoint
      const { ticket } = await fetchApi<{ ticket: string }>('/api/auth/ws-ticket', {
        method: 'POST',
      })

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/admin/ws?ticket=${ticket}`
      )

      ws.onopen = () => {
        setState('connected')
        backoffRef.current = INITIAL_BACKOFF
        // Skip the first open (initial load); fire onReconnect on every
        // subsequent open so reconnected tabs resync missed events (D2).
        if (hasConnectedRef.current) {
          onReconnectRef.current?.()
        } else {
          hasConnectedRef.current = true
        }
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' } satisfies WSControl))
            return
          }
          if (data.type === 'event' && onEvent) {
            onEvent(data as WSEvent)
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = () => {
        setState('disconnected')
        wsRef.current = null
        scheduleReconnectRef.current?.()
      }

      ws.onerror = () => {
        setState('error')
        ws.close()
      }

      wsRef.current = ws
    } catch {
      setState('error')
      scheduleReconnectRef.current?.()
    }
  }, [onEvent])

  const scheduleReconnect = useCallback(() => {
    if (!enabledRef.current) return
    const delay = backoffRef.current
    backoffRef.current = Math.min(delay * 2, MAX_BACKOFF)
    reconnectTimerRef.current = setTimeout(() => {
      connect()
    }, delay)
  }, [connect])

  // Keep ref in sync with latest scheduleReconnect
  useEffect(() => {
    scheduleReconnectRef.current = scheduleReconnect
  }, [scheduleReconnect])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setState('disconnected')
  }, [])

  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      disconnect()
    }
    return () => {
      disconnect()
    }
  }, [enabled, connect, disconnect])

  return { state, disconnect }
}
