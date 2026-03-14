import { useEffect, useRef, useCallback, useState } from 'react'
import { fetchApi } from '../api/client'
import type { WSEvent, WSControl } from '../api/types'

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketOptions {
  onEvent?: (event: WSEvent) => void
  enabled?: boolean
}

const MAX_BACKOFF = 30_000
const INITIAL_BACKOFF = 1_000

export function useWebSocket({ onEvent, enabled = true }: UseWebSocketOptions = {}) {
  const [state, setState] = useState<ConnectionState>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef(INITIAL_BACKOFF)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

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
        scheduleReconnect()
      }

      ws.onerror = () => {
        setState('error')
        ws.close()
      }

      wsRef.current = ws
    } catch {
      setState('error')
      scheduleReconnect()
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
