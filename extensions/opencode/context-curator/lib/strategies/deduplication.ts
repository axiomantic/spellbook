import type { Logger } from "../logger.js";
import type { CuratorConfig, SessionState, WithParts } from "../types.js";
import {
  buildToolIdList,
  calculateTokensSaved,
  getFilePathFromParameters,
  isProtectedFilePath,
} from "./utils.js";

/**
 * Deduplication strategy - prunes older tool calls with identical tool name and parameters
 */
export function deduplicate(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  messages: WithParts[]
): void {
  if (!config.strategies.deduplication.enabled) {
    return;
  }

  const allToolIds = buildToolIdList(state, messages);
  if (allToolIds.length === 0) return;

  const alreadyPruned = new Set(state.prune.toolIds);
  const unprunedIds = allToolIds.filter((id) => !alreadyPruned.has(id));
  if (unprunedIds.length === 0) return;

  const protectedTools = config.strategies.deduplication.protectedTools;
  const signatureMap = new Map<string, string[]>();

  for (const id of unprunedIds) {
    const metadata = state.toolParameters.get(id);
    if (!metadata) continue;

    if (protectedTools.includes(metadata.tool)) continue;

    const filePath = getFilePathFromParameters(metadata.parameters);
    if (isProtectedFilePath(filePath, config.protectedFilePatterns)) continue;

    const signature = createToolSignature(metadata.tool, metadata.parameters);
    if (!signatureMap.has(signature)) {
      signatureMap.set(signature, []);
    }
    signatureMap.get(signature)!.push(id);
  }

  const newPruneIds: string[] = [];

  for (const [, ids] of signatureMap.entries()) {
    if (ids.length > 1) {
      const idsToRemove = ids.slice(0, -1);
      newPruneIds.push(...idsToRemove);
    }
  }

  if (newPruneIds.length > 0) {
    const tokensSaved = calculateTokensSaved(state, messages, newPruneIds);
    state.stats.totalPruneTokens += tokensSaved;
    state.stats.prunesByStrategy["deduplication"] =
      (state.stats.prunesByStrategy["deduplication"] || 0) + newPruneIds.length;

    state.prune.toolIds.push(...newPruneIds);
    logger.debugLog(`Marked ${newPruneIds.length} duplicate tool calls for pruning`, {
      tokensSaved,
    });
  }
}

function createToolSignature(
  tool: string,
  parameters?: Record<string, unknown>
): string {
  if (!parameters) return tool;
  const normalized = normalizeParameters(parameters);
  const sorted = sortObjectKeys(normalized);
  return `${tool}::${JSON.stringify(sorted)}`;
}

function normalizeParameters(
  params: Record<string, unknown>
): Record<string, unknown> {
  const normalized: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      normalized[key] = value;
    }
  }
  return normalized;
}

function sortObjectKeys(obj: unknown): unknown {
  if (typeof obj !== "object" || obj === null) return obj;
  if (Array.isArray(obj)) return obj.map(sortObjectKeys);

  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(obj as Record<string, unknown>).sort()) {
    sorted[key] = sortObjectKeys((obj as Record<string, unknown>)[key]);
  }
  return sorted;
}
