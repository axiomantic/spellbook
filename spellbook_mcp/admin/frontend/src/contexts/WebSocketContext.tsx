import { createContext, useContext, useCallback, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from '../hooks/useWebSocket'
import type { WSEvent } from '../api/types'

interface WebSocketContextValue {
  /** Current connection state. */
  isConnected: boolean
  /** Raw connection state string for detailed status display. */
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error'
  /** Most recent event received over the WebSocket. */
  lastEvent: WSEvent | null
  /** Rolling buffer of the most recent events (newest first, max 50). */
  events: WSEvent[]
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

const MAX_EVENTS = 50

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)
  const [events, setEvents] = useState<WSEvent[]>([])

  const handleEvent = useCallback(
    (event: WSEvent) => {
      setLastEvent(event)
      setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS))

      // Invalidate relevant query caches based on subsystem
      switch (event.subsystem) {
        case 'memory':
          queryClient.invalidateQueries({ queryKey: ['memories'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          break
        case 'config':
          queryClient.invalidateQueries({ queryKey: ['config'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          break
        case 'security':
          queryClient.invalidateQueries({ queryKey: ['security'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          break
        case 'session':
          queryClient.invalidateQueries({ queryKey: ['sessions'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          break
        case 'fractal':
          queryClient.invalidateQueries({ queryKey: ['fractal'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
          break
        default:
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      }
    },
    [queryClient],
  )

  const { state } = useWebSocket({ onEvent: handleEvent })

  const value: WebSocketContextValue = {
    isConnected: state === 'connected',
    connectionState: state,
    lastEvent,
    events,
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocketContext(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext)
  if (!ctx) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider')
  }
  return ctx
}
