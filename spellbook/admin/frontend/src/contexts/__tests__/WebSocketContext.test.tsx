import { render, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createElement, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WebSocketProvider } from '../WebSocketContext'
import type { WSEvent } from '../../api/types'

/**
 * Tests for the WebSocketProvider event-dispatch logic, specifically the
 * `case 'canvas':` arm added by Track B.3.
 *
 * Approach:
 *   - Stub `global.fetch` so `useWebSocket`'s `fetchApi('/api/auth/ws-ticket')`
 *     resolves and the provider proceeds to construct a WebSocket.
 *   - Replace `global.WebSocket` with a controllable fake that captures
 *     `onmessage`. The test then invokes `onmessage` with a synthetic
 *     `MessageEvent` whose `data` is the JSON-stringified WS frame.
 *   - Spy on `QueryClient.invalidateQueries` and assert the exact calls.
 */

interface FakeWS {
  onopen: ((this: WebSocket, ev: Event) => unknown) | null
  onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null
  onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null
  onerror: ((this: WebSocket, ev: Event) => unknown) | null
  readyState: number
  send: (data: string) => void
  close: () => void
  url: string
}

let lastFakeWs: FakeWS | null = null

class FakeWebSocket implements FakeWS {
  onopen: ((this: WebSocket, ev: Event) => unknown) | null = null
  onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null
  onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null
  onerror: ((this: WebSocket, ev: Event) => unknown) | null = null
  readyState = 1
  url: string
  send = vi.fn()
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    lastFakeWs = this
    // Fire onopen in a microtask so callers can wire onmessage first if needed.
    queueMicrotask(() => {
      this.onopen?.call(this as unknown as WebSocket, new Event('open'))
    })
  }
}

function stubWsTicket() {
  // useWebSocket calls fetchApi('/api/auth/ws-ticket', { method: 'POST' }),
  // which becomes fetch('/admin/api/auth/ws-ticket', { method: 'POST', ... }).
  return vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ ticket: 'test-ticket' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  })
}

function Wrap({ client, children }: { client: QueryClient; children: ReactNode }) {
  return createElement(
    QueryClientProvider,
    { client },
    createElement(WebSocketProvider, null, children),
  )
}

async function waitForWs(): Promise<FakeWS> {
  await waitFor(() => {
    expect(lastFakeWs).not.toBeNull()
  })
  return lastFakeWs!
}

async function deliverFrame(ws: FakeWS, frame: object) {
  await act(async () => {
    ws.onmessage?.call(
      ws as unknown as WebSocket,
      new MessageEvent('message', { data: JSON.stringify(frame) }),
    )
  })
}

describe('WebSocketProvider — canvas dispatch (B.3)', () => {
  let originalWebSocket: typeof WebSocket

  beforeEach(() => {
    lastFakeWs = null
    originalWebSocket = global.WebSocket
    // @ts-expect-error — replacing the constructor with a fake
    global.WebSocket = FakeWebSocket
    stubWsTicket()
  })

  afterEach(() => {
    global.WebSocket = originalWebSocket
    vi.restoreAllMocks()
  })

  it('canvas frame invalidates [canvas], [canvas, <name>], and [dashboard]', async () => {
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))
    const ws = await waitForWs()

    const frame: WSEvent = {
      type: 'event',
      subsystem: 'canvas',
      event: 'updated',
      data: { canvas: 'demo' },
      timestamp: '2026-05-14T10:00:00Z',
    }
    await deliverFrame(ws, frame)

    // Three invalidations, in this exact order.
    expect(invalidateSpy).toHaveBeenCalledTimes(3)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, { queryKey: ['canvas'] })
    expect(invalidateSpy).toHaveBeenNthCalledWith(2, {
      queryKey: ['canvas', 'demo'],
    })
    expect(invalidateSpy).toHaveBeenNthCalledWith(3, {
      queryKey: ['dashboard'],
    })
  })

  it('canvas frame without `data.canvas` invalidates [canvas] and [dashboard] only (no per-name key)', async () => {
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))
    const ws = await waitForWs()

    const frame: WSEvent = {
      type: 'event',
      subsystem: 'canvas',
      event: 'list_refreshed',
      data: {},
      timestamp: '2026-05-14T10:00:00Z',
    }
    await deliverFrame(ws, frame)

    expect(invalidateSpy).toHaveBeenCalledTimes(2)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, { queryKey: ['canvas'] })
    expect(invalidateSpy).toHaveBeenNthCalledWith(2, {
      queryKey: ['dashboard'],
    })
  })

  it('non-canvas frame (subsystem=memory) does NOT invalidate any [canvas] key', async () => {
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))
    const ws = await waitForWs()

    const frame: WSEvent = {
      type: 'event',
      subsystem: 'memory',
      event: 'updated',
      data: { canvas: 'should-be-ignored' },
      timestamp: '2026-05-14T10:00:00Z',
    }
    await deliverFrame(ws, frame)

    // memory arm: invalidate ['memories'] and ['dashboard']. NO ['canvas'].
    expect(invalidateSpy).toHaveBeenCalledTimes(2)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, {
      queryKey: ['memories'],
    })
    expect(invalidateSpy).toHaveBeenNthCalledWith(2, {
      queryKey: ['dashboard'],
    })

    // No call mentioned the 'canvas' key in any position.
    const allKeys = invalidateSpy.mock.calls.map(([arg]) =>
      (arg as { queryKey: unknown[] }).queryKey.join('|'),
    )
    expect(allKeys).not.toContain('canvas')
    expect(allKeys).not.toContain('canvas|should-be-ignored')
  })
})
