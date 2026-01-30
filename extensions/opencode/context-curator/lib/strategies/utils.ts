import { countTokens } from "@anthropic-ai/tokenizer";
import type { SessionState, WithParts } from "../types.js";

/**
 * Build list of all tool call IDs from messages in chronological order
 */
export function buildToolIdList(
  state: SessionState,
  messages: WithParts[]
): string[] {
  const ids: string[] = [];

  for (const msg of messages) {
    if (msg.info.time.created <= state.lastCompaction) {
      continue;
    }

    const parts = Array.isArray(msg.parts) ? msg.parts : [];
    for (const part of parts) {
      if (part.type === "tool" && part.callID) {
        ids.push(part.callID);
      }
    }
  }

  return ids;
}

/**
 * Calculate tokens saved by pruning given tool IDs
 */
export function calculateTokensSaved(
  state: SessionState,
  messages: WithParts[],
  toolIds: string[]
): number {
  let tokens = 0;
  const idsSet = new Set(toolIds);

  for (const msg of messages) {
    const parts = Array.isArray(msg.parts) ? msg.parts : [];
    for (const part of parts) {
      if (part.type === "tool" && part.callID && idsSet.has(part.callID)) {
        const content = JSON.stringify(part);
        tokens += countTokens(content);
      }
    }
  }

  return tokens;
}

/**
 * Get file path from tool parameters
 */
export function getFilePathFromParameters(
  parameters: Record<string, unknown>
): string | null {
  const pathKeys = ["file_path", "filePath", "path", "file"];

  for (const key of pathKeys) {
    const value = parameters[key];
    if (typeof value === "string") {
      return value;
    }
  }

  return null;
}

/**
 * Check if file path matches any protected pattern
 */
export function isProtectedFilePath(
  filePath: string | null,
  patterns: string[]
): boolean {
  if (!filePath) return false;

  for (const pattern of patterns) {
    const regex = pattern.replace(/\*\*/g, ".*").replace(/\*/g, "[^/]*");

    if (new RegExp(regex).test(filePath)) {
      return true;
    }
  }

  return false;
}
