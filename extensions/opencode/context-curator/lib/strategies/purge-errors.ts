import type { Logger } from "../logger.js";
import type { CuratorConfig, SessionState, WithParts } from "../types.js";
import { buildToolIdList, calculateTokensSaved } from "./utils.js";

/**
 * Purge Errors strategy - removes errored tool inputs after N turns.
 */
export function purgeErrors(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  messages: WithParts[]
): void {
  if (!config.strategies.purgeErrors.enabled) {
    return;
  }
  
  const threshold = config.strategies.purgeErrors.turnThreshold;
  const allToolIds = buildToolIdList(state, messages);
  
  if (allToolIds.length === 0) return;
  
  const alreadyPruned = new Set(state.prune.toolIds);
  const newPruneIds: string[] = [];
  
  for (const id of allToolIds) {
    if (alreadyPruned.has(id)) continue;
    
    const metadata = state.toolParameters.get(id);
    if (!metadata) continue;
    
    if (metadata.status === "error" || metadata.error) {
      const turnsSinceError = state.currentTurn - metadata.turn;
      if (turnsSinceError >= threshold) {
        newPruneIds.push(id);
      }
    }
  }
  
  if (newPruneIds.length > 0) {
    const tokensSaved = calculateTokensSaved(state, messages, newPruneIds);
    state.stats.totalPruneTokens += tokensSaved;
    state.stats.prunesByStrategy["purgeErrors"] = 
      (state.stats.prunesByStrategy["purgeErrors"] || 0) + newPruneIds.length;
    
    state.prune.toolIds.push(...newPruneIds);
    logger.debugLog(`Marked ${newPruneIds.length} errored tool calls for pruning`, { tokensSaved, threshold });
  }
}
