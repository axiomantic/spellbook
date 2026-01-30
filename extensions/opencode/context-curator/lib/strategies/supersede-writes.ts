import type { Logger } from "../logger.js";
import type { CuratorConfig, SessionState, WithParts } from "../types.js";
import { buildToolIdList, calculateTokensSaved, getFilePathFromParameters, isProtectedFilePath } from "./utils.js";

/**
 * Supersede Writes strategy - prunes write tool inputs for files that have
 * subsequently been read.
 */
export function supersedeWrites(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  messages: WithParts[]
): void {
  if (!config.strategies.supersedeWrites.enabled) {
    return;
  }
  
  const allToolIds = buildToolIdList(state, messages);
  if (allToolIds.length === 0) return;
  
  const alreadyPruned = new Set(state.prune.toolIds);
  
  const writesByFile = new Map<string, { id: string; index: number }[]>();
  const readsByFile = new Map<string, number[]>();
  
  for (let i = 0; i < allToolIds.length; i++) {
    const id = allToolIds[i];
    const metadata = state.toolParameters.get(id);
    if (!metadata) continue;
    
    const filePath = getFilePathFromParameters(metadata.parameters);
    if (!filePath) continue;
    
    if (isProtectedFilePath(filePath, config.protectedFilePatterns)) continue;
    
    if (metadata.tool === "write" || metadata.tool === "Write") {
      if (!writesByFile.has(filePath)) {
        writesByFile.set(filePath, []);
      }
      writesByFile.get(filePath)!.push({ id, index: i });
    } else if (metadata.tool === "read" || metadata.tool === "Read") {
      if (!readsByFile.has(filePath)) {
        readsByFile.set(filePath, []);
      }
      readsByFile.get(filePath)!.push(i);
    }
  }
  
  const newPruneIds: string[] = [];
  
  for (const [filePath, writes] of writesByFile.entries()) {
    const reads = readsByFile.get(filePath);
    if (!reads || reads.length === 0) continue;
    
    for (const write of writes) {
      if (alreadyPruned.has(write.id)) continue;
      
      const hasSubsequentRead = reads.some((readIndex) => readIndex > write.index);
      if (hasSubsequentRead) {
        newPruneIds.push(write.id);
      }
    }
  }
  
  if (newPruneIds.length > 0) {
    const tokensSaved = calculateTokensSaved(state, messages, newPruneIds);
    state.stats.totalPruneTokens += tokensSaved;
    state.stats.prunesByStrategy["supersedeWrites"] = 
      (state.stats.prunesByStrategy["supersedeWrites"] || 0) + newPruneIds.length;
    
    state.prune.toolIds.push(...newPruneIds);
    logger.debugLog(`Marked ${newPruneIds.length} superseded write tool calls for pruning`, { tokensSaved });
  }
}
