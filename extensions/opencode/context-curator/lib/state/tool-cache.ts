import type { CuratorConfig } from "../types.js";
import type { Logger } from "../logger.js";
import type { SessionState, WithParts, ToolParameterEntry } from "../types.js";
import type { Part } from "@opencode-ai/sdk/v2";

function isToolPart(part: Part): part is Part & { type: "tool"; callID: string; tool: string; state: { status: string; input?: Record<string, unknown>; error?: string } } {
  return part.type === "tool" && "callID" in part;
}

export function syncToolCache(
  state: SessionState,
  config: CuratorConfig,
  logger: Logger,
  messages: WithParts[]
): void {
  let newEntries = 0;
  
  for (const msg of messages) {
    if (msg.info.time.created <= state.lastCompaction) continue;
    
    const parts = msg.parts;
    if (!Array.isArray(parts)) continue;
    
    for (const part of parts) {
      if (isToolPart(part)) {
        const id = part.callID;
        
        if (state.toolParameters.has(id)) continue;
        
        const entry: ToolParameterEntry = {
          tool: part.tool || "unknown",
          parameters: extractParameters(part),
          status: extractStatus(part),
          error: extractError(part),
          turn: state.currentTurn,
          timestamp: msg.info.time.created,
        };
        
        state.toolParameters.set(id, entry);
        newEntries++;
      }
    }
  }
  
  if (newEntries > 0) {
    logger.debugLog(`Synced ${newEntries} new tool invocations to cache`);
  }
}

function extractParameters(part: { state?: { input?: Record<string, unknown> } }): Record<string, unknown> {
  if (part.state?.input && typeof part.state.input === "object") {
    return part.state.input;
  }
  return {};
}

function extractStatus(part: { state?: { status?: string } }): "pending" | "running" | "completed" | "error" {
  const status = part.state?.status;
  if (status === "pending" || status === "running" || status === "completed" || status === "error") {
    return status;
  }
  return "completed";
}

function extractError(part: { state?: { error?: string } }): string | undefined {
  if (part.state && "error" in part.state) {
    const error = part.state.error;
    return typeof error === "string" ? error : undefined;
  }
  return undefined;
}
