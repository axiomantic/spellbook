import type { Part } from "@opencode-ai/sdk";
import type { CuratorConfig } from "../types.js";
import type { Logger } from "../logger.js";
import type { SessionState, WithParts } from "../types.js";
import { isMessageCompacted } from "./utils.js";

function isToolPart(part: Part): part is Part & { type: "tool"; callID: string } {
  return part.type === "tool" && "callID" in part;
}

function buildPrunableList(
  state: SessionState,
  config: CuratorConfig,
  messages: WithParts[]
): string[] {
  const pruneSet = new Set(state.prune.toolIds);
  const prunableIds: string[] = [];
  
  for (const msg of messages) {
    if (isMessageCompacted(state, msg)) continue;
    
    const parts = msg.parts;
    if (!Array.isArray(parts)) continue;
    
    for (const part of parts) {
      if (isToolPart(part)) {
        if (!pruneSet.has(part.callID) && state.toolParameters.has(part.callID)) {
          prunableIds.push(part.callID);
        }
      }
    }
  }
  
  return prunableIds;
}

export function insertPruneToolContext(
  state: SessionState,
  config: CuratorConfig,
  logger: Logger,
  messages: WithParts[]
): void {
  if (!config.tools.discard.enabled && !config.tools.extract.enabled) return;
  
  const prunableIds = buildPrunableList(state, config, messages);
  if (prunableIds.length === 0) return;
  
  const toolDetails = prunableIds.map((id) => {
    const metadata = state.toolParameters.get(id);
    if (!metadata) return null;
    return `  <tool id="${id}" name="${metadata.tool}" turn="${metadata.turn}" />`;
  }).filter(Boolean);
  
  if (toolDetails.length === 0) return;
  
  const contextXml = `<prunable-tools count="${toolDetails.length}">\n${toolDetails.join("\n")}\n</prunable-tools>`;
  
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg?.info.role === "assistant" && !isMessageCompacted(state, msg)) {
      if (Array.isArray(msg.parts)) {
        msg.parts.push({ type: "text", text: contextXml } as Part);
      }
      logger.debugLog(`Injected prunable-tools context with ${toolDetails.length} tools`);
      return;
    }
  }
}
