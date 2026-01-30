import { countTokens } from "@anthropic-ai/tokenizer";
import type { Logger } from "../logger.js";
import type { SessionState, WithParts } from "../types.js";

export interface ContextCommandDeps {
  state: SessionState;
  logger: Logger;
  messages: WithParts[];
}

export async function handleContextCommand(deps: ContextCommandDeps): Promise<string> {
  const { state, messages } = deps;
  
  const totalMessages = messages.length;
  let totalTokens = 0;
  let toolInvocations = 0;
  let prunedInvocations = 0;
  
  const pruneSet = new Set(state.prune.toolIds);
  
  for (const msg of messages) {
    const parts = msg.parts;
    if (!Array.isArray(parts)) continue;
    
    for (const part of parts) {
      const content = JSON.stringify(part);
      totalTokens += countTokens(content);
      
      if (part.type === "tool" && part.callID) {
        toolInvocations++;
        if (pruneSet.has(part.callID)) {
          prunedInvocations++;
        }
      }
    }
  }
  
  const prunableCount = state.toolParameters.size - pruneSet.size;
  
  return `
## Context Curator Status

**Messages:** ${totalMessages}
**Estimated Tokens:** ~${totalTokens.toLocaleString()}

**Tool Invocations:**
- Total: ${toolInvocations}
- Pruned: ${prunedInvocations}
- Prunable: ${prunableCount}

**Tokens Saved:** ~${state.stats.totalPruneTokens.toLocaleString()}
`.trim();
}
