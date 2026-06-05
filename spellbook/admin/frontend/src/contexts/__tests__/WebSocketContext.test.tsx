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
 *   - Stub `globalThis.fetch` so `useWebSocket`'s `fetchApi('/api/auth/ws-ticket')`
 *     resolves and the provider proceeds to construct a WebSocket.
 *   - Replace `globalThis.WebSocket` with a controllable fake that captures
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

  private static register(instance: FakeWebSocket) {
    lastFakeWs = instance
  }

  constructor(url: string) {
    this.url = url
    FakeWebSocket.register(this)
    // Fire onopen in a microtask so callers can wire onmessage first if needed.
    queueMicrotask(() => {
      this.onopen?.call(this as unknown as WebSocket, new Event('open'))
    })
  }
}

function stubWsTicket() {
  // useWebSocket calls fetchApi('/api/auth/ws-ticket', { method: 'POST' }),
  // which becomes fetch('/admin/api/auth/ws-ticket', { method: 'POST', ... }).
  // Return a FRESH Response per call: a Response body can be read only once, so
  // a reused instance would make the SECOND connect (reconnect) fail at
  // `.json()` — masking the reconnect path. In production every fetch yields a
  // fresh Response, so per-call construction matches reality.
  return vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify({ ticket: 'test-ticket' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
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
    originalWebSocket = globalThis.WebSocket
    // @ts-expect-error — replacing the constructor with a fake
    globalThis.WebSocket = FakeWebSocket
    stubWsTicket()
  })

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket
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

  it('canvas.decision.submitted invalidates the per-canvas query key (second-tab live update)', async () => {
    // finding #7 / I6: decision events REUSE the canvas subsystem so the
    // existing `case 'canvas':` per-name invalidation fires for any open tab,
    // making a SECOND tab go submitted/already_decided live. The load-bearing
    // regression guard is `subsystem === 'canvas'` — if a decision event ever
    // introduced a new subsystem, it would miss the canvas handler and the
    // per-name `['canvas', name]` key would never invalidate.
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))
    const ws = await waitForWs()

    const frame: WSEvent = {
      type: 'event',
      subsystem: 'canvas', // REGRESSION GUARD: must stay 'canvas'
      event: 'canvas.decision.submitted',
      data: { canvas: 'plan-x', decision_id: 'd1', value: 'a' },
      timestamp: '2026-06-04T18:22:01Z',
    }
    await deliverFrame(ws, frame)

    // Same three canvas invalidations, in this exact order — the per-name
    // `['canvas', 'plan-x']` key is what drives the second-tab live update.
    expect(invalidateSpy).toHaveBeenCalledTimes(3)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, { queryKey: ['canvas'] })
    expect(invalidateSpy).toHaveBeenNthCalledWith(2, {
      queryKey: ['canvas', 'plan-x'],
    })
    expect(invalidateSpy).toHaveBeenNthCalledWith(3, {
      queryKey: ['dashboard'],
    })
  })

  // D2: on a WS RECONNECT (close → backoff → reopen), the provider must
  // invalidate the ['canvas'] query so a tab that was offline during a decision
  // event resyncs the missed state. The FIRST connect must NOT invalidate
  // (initial data load is the query's own job; invalidating then would be a
  // redundant double-fetch on mount).
  it('invalidates [canvas] on reconnect but NOT on the first connect', async () => {
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))

    // First connect: the FakeWebSocket constructs and fires its
    // queued-microtask onopen. Flush microtasks so onopen runs.
    const firstWs = await waitForWs()
    await act(async () => {
      await Promise.resolve()
    })

    // First connect performed no canvas invalidation.
    expect(invalidateSpy).not.toHaveBeenCalled()

    // Drop the connection. onclose schedules a reconnect via setTimeout
    // (INITIAL_BACKOFF = 1000ms). Real timers are in play; the backoff is short,
    // so wait it out. connect() then awaits the ws-ticket fetch (resolved
    // Promise) and constructs a NEW FakeWebSocket whose queued-microtask onopen
    // runs onReconnect → invalidate(['canvas']).
    await act(async () => {
      firstWs.onclose?.call(firstWs as unknown as WebSocket, new CloseEvent('close'))
    })
    await waitFor(
      () => {
        expect(lastFakeWs).not.toBe(firstWs)
      },
      { timeout: 3000 },
    )
    // Flush the reconnect socket's queued-microtask onopen.
    await act(async () => {
      await Promise.resolve()
    })

    // Exactly one invalidation, with the exact ['canvas'] key, fired on the
    // reconnect open — and none on the first connect.
    expect(invalidateSpy).toHaveBeenCalledTimes(1)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, { queryKey: ['canvas'] })
  })

  it('non-canvas frame (unhandled subsystem) does NOT invalidate any [canvas] key', async () => {
    const client = makeClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')

    render(createElement(Wrap, { client, children: null }))
    const ws = await waitForWs()

    const frame: WSEvent = {
      type: 'event',
      subsystem: 'unhandled',
      event: 'updated',
      data: { canvas: 'should-be-ignored' },
      timestamp: '2026-05-14T10:00:00Z',
    }
    await deliverFrame(ws, frame)

    // default arm: invalidate only ['dashboard']. NO ['canvas'].
    expect(invalidateSpy).toHaveBeenCalledTimes(1)
    expect(invalidateSpy).toHaveBeenNthCalledWith(1, {
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
