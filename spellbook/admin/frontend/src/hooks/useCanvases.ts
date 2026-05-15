import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { CanvasListResponse, CanvasDetail } from '../api/types'

/**
 * List all canvases.
 *
 * Backed by `GET /admin/api/canvas` (see `spellbook/admin/routes/canvas.py`).
 * Re-fetches automatically when the WebSocket layer invalidates the
 * `['canvas']` query key (see WebSocketContext `case 'canvas':`).
 */
export function useCanvasList() {
  return useQuery({
    queryKey: ['canvas'],
    queryFn: () => fetchApi<CanvasListResponse>('/api/canvas'),
  })
}

/**
 * Read a single canvas by name.
 *
 * Backed by `GET /admin/api/canvas/:name`. Disabled when `name` is null so
 * route component can render a placeholder before the route param resolves.
 */
export function useCanvas(name: string | null) {
  return useQuery({
    queryKey: ['canvas', name],
    queryFn: () =>
      fetchApi<CanvasDetail>(`/api/canvas/${encodeURIComponent(name!)}`),
    enabled: !!name,
  })
}
