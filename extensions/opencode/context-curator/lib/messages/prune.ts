import type { Part } from "@opencode-ai/sdk";
import type { CuratorConfig } from "../types.js";
import type { Logger } from "../logger.js";
import type { SessionState, WithParts } from "../types.js";
import { isMessageCompacted } from "./utils.js";

function isToolPart(part: Part): part is Part & { type: "tool"; callID: string; state: { output?: string } } {
  return part.type === "tool" && "callID" in part;
}

export function prune(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  messages: WithParts[]
): void {
  if (state.prune.toolIds.length === 0) return;
  
  const pruneSet = new Set(state.prune.toolIds);
  let prunedCount = 0;
  
  for (const msg of messages) {
    if (isMessageCompacted(state, msg)) continue;
    
    const parts = msg.parts;
    if (!Array.isArray(parts)) continue;
    
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      
      if (isToolPart(part)) {
        if (pruneSet.has(part.callID)) {
          const summary = state.extracts.summaries.get(part.callID);
          
          if (summary) {
            parts[i] = { ...part, state: { ...part.state, output: `[EXTRACTED] ${summary}` } } as Part;
          } else {
            parts[i] = { ...part, state: { ...part.state, output: "[PRUNED - content removed to save context]" } } as Part;
          }
          
          prunedCount++;
        }
      }
    }
  }
  
  if (prunedCount > 0) {
    logger.debugLog(`Applied pruning to ${prunedCount} tool invocations`);
  }
}
