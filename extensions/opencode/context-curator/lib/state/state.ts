import type { SessionState, WithParts } from "../types.js";
import { CURRENT_SCHEMA_VERSION } from "./version.js";

/**
 * Create fresh session state
 */
export function createSessionState(): SessionState {
  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    sessionId: null,
    isSubAgent: false,
    prune: {
      toolIds: [],
      pendingTokenCalc: [],
    },
    extracts: {
      summaries: new Map(),
    },
    stats: {
      pruneTokenCounter: 0,
      totalPruneTokens: 0,
      prunesByStrategy: {},
    },
    toolParameters: new Map(),
    lastCompaction: 0,
    currentTurn: 0,
    variant: undefined,
  };
}

/**
 * Reset session state to fresh values
 */
export function resetSessionState(state: SessionState): void {
  state.schemaVersion = CURRENT_SCHEMA_VERSION;
  state.sessionId = null;
  state.isSubAgent = false;
  state.prune = { toolIds: [], pendingTokenCalc: [] };
  state.extracts = { summaries: new Map() };
  state.stats = {
    pruneTokenCounter: 0,
    totalPruneTokens: 0,
    prunesByStrategy: {},
  };
  state.toolParameters.clear();
  state.lastCompaction = 0;
  state.currentTurn = 0;
  state.variant = undefined;
}

/**
 * Check if session is a subagent (should skip pruning)
 */
export async function isSubAgentSession(
  client: { session: { get: (opts: { path: { id: string } }) => Promise<{ data?: { parent?: string } }> } },
  sessionId: string
): Promise<boolean> {
  try {
    const response = await client.session.get({ path: { id: sessionId } });
    return Boolean(response.data?.parent);
  } catch {
    return false;
  }
}

/**
 * Find timestamp of last compaction in messages
 */
export function findLastCompactionTimestamp(messages: WithParts[]): number {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg?.info.role === "assistant" && msg.info.summary === true) {
      return msg.info.time.created;
    }
  }
  return 0;
}

/**
 * Count conversation turns from messages
 */
export function countTurns(state: SessionState, messages: WithParts[]): number {
  let turnCount = 0;

  for (const msg of messages) {
    // Skip messages before last compaction
    if (msg.info.time.created <= state.lastCompaction) {
      continue;
    }

    const parts = Array.isArray(msg.parts) ? msg.parts : [];
    for (const part of parts) {
      if (part.type === "step-start") {
        turnCount++;
      }
    }
  }

  return turnCount;
}
