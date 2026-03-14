import { useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from './useWebSocket'
import type { WSEvent } from '../api/types'

/**
 * Combines WebSocket connection with TanStack Query cache invalidation.
 * Events from the bus trigger targeted query refetches so the UI stays fresh.
 */
export function useEventStream() {
  const queryClient = useQueryClient()

  const handleEvent = useCallback(
    (event: WSEvent) => {
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
          // Unknown subsystem, refresh dashboard as fallback
          queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      }
    },
    [queryClient]
  )

  return useWebSocket({ onEvent: handleEvent })
}
