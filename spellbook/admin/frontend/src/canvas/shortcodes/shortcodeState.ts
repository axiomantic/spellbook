/**
 * Remount-survival state cache for stateful display shortcodes (design §4.3,
 * Task 13). Every `canvas_write` invalidates the canvas query and remounts
 * `CanvasRender`'s shortcode leaves, resetting any local `useState`. These
 * module-scoped maps cache each leaf's UI state keyed by a stable identity
 * (canvas name + summary/titles + source byte offset), read on mount and
 * written on change, so open/active state survives the remount.
 *
 * The cache is bounded by:
 *   - a per-canvas eviction sweep on `CanvasDetail` unmount (`evictCanvasShortcodeState`), and
 *   - the `__resetCanvasShortcodeState` test hook cleared in `beforeEach`.
 *
 * Deliberately deferred: design §4.3's third bound — orphan-prune-on-write for
 * superseded keys — is NOT implemented. Per-canvas namespacing plus the
 * unmount sweep are the shipping bounds, so the cache grows only within one
 * live canvas view (stale keys for an edited-away shortcode persist until that
 * canvas unmounts).
 */

/** Collapsible open/closed state, keyed by `${canvasName}::${summary}::${offset}`. */
export const collapsibleOpenState = new Map<string, boolean>()

/** Tabs active-index state, keyed by `${canvasName}::${joinedTitles}::${offset}`. */
export const tabsActiveState = new Map<string, number>()

/**
 * Test hook (RT-1): clears BOTH module-scoped caches. MUST be called in
 * `beforeEach` of any test mounting a stateful shortcode, otherwise cached
 * state leaks across tests and breaks default-closed / default-first-tab
 * assertions.
 */
export function __resetCanvasShortcodeState(): void {
  collapsibleOpenState.clear()
  tabsActiveState.clear()
}

/**
 * Evict every cached entry for a given canvas (the `CanvasDetail`-unmount
 * sweep, design §4.3 / F3). Keys are prefixed with `${canvasName}::`, so a
 * prefix scan removes exactly that canvas's entries and leaves other canvases'
 * state intact.
 */
export function evictCanvasShortcodeState(canvasName: string): void {
  const prefix = `${canvasName}::`
  for (const k of collapsibleOpenState.keys()) {
    if (k.startsWith(prefix)) collapsibleOpenState.delete(k)
  }
  for (const k of tabsActiveState.keys()) {
    if (k.startsWith(prefix)) tabsActiveState.delete(k)
  }
}
