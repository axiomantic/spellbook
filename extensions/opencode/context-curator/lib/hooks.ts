import type { CuratorConfig } from "./types.js";
import type { Logger } from "./logger.js";
import type { SessionState, WithParts } from "./types.js";
import type { McpClient } from "./mcp-client.js";
import {
  createSessionState,
  resetSessionState,
  isSubAgentSession,
  findLastCompactionTimestamp,
  countTurns,
  syncToolCache,
} from "./state/index.js";
import { deduplicate, supersedeWrites, purgeErrors } from "./strategies/index.js";
import { prune, insertPruneToolContext, getLastUserMessage, calculateTokenSavings } from "./messages/index.js";
import { getSystemPrompt } from "./prompts/system.js";

const INTERNAL_AGENT_SIGNATURES = [
  "You are a title generator",
  "You are a helpful AI assistant tasked with summarizing conversations",
  "Summarize what was done in this conversation",
];

export function createSystemPromptHandler(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig
) {
  return async (_input: unknown, output: { system: string[] }) => {
    if (state.isSubAgent) return;

    const systemText = output.system.join("\n");
    if (INTERNAL_AGENT_SIGNATURES.some((sig) => systemText.includes(sig))) {
      logger.debugLog("Skipping system prompt injection for internal agent");
      return;
    }

    const prompt = getSystemPrompt(config.tools.discard.enabled, config.tools.extract.enabled);

    if (prompt) {
      output.system.push(prompt);
      logger.debugLog("Injected context management system prompt");
    }
  };
}

export function createChatMessageTransformHandler(
  client: any,
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  mcpClient: McpClient
) {
  return async (_input: {}, output: { messages: WithParts[] }) => {
    await checkSession(client, state, logger, output.messages);

    if (state.isSubAgent) {
      logger.debugLog("Skipping pruning for subagent session");
      return;
    }

    syncToolCache(state, config, logger, output.messages);

    deduplicate(state, logger, config, output.messages);
    supersedeWrites(state, logger, config, output.messages);
    purgeErrors(state, logger, config, output.messages);

    // Process pending manual discards/extracts and calculate their token savings
    if (state.prune.pendingTokenCalc.length > 0) {
      const pendingIds = [...state.prune.pendingTokenCalc];
      const tokensSaved = calculateTokenSavings(pendingIds, output.messages, state);
      
      if (tokensSaved > 0) {
        state.stats.totalPruneTokens += tokensSaved;
        logger.debugLog(`Calculated ${tokensSaved} tokens saved from manual prune`, { ids: pendingIds });
      }
      
      // Track to MCP server
      if (state.sessionId && tokensSaved > 0) {
        // Determine strategy based on whether extracts exist
        const hasExtracts = pendingIds.some(id => state.extracts.summaries.has(id));
        const strategy = hasExtracts ? "extract" : "discard";
        mcpClient
          .trackPrune(state.sessionId, pendingIds, tokensSaved, strategy)
          .catch(() => {});
      }
      
      // Clear pending list
      state.prune.pendingTokenCalc = [];
    }

    prune(state, logger, config, output.messages);
    insertPruneToolContext(state, config, logger, output.messages);

    if (state.sessionId && state.stats.totalPruneTokens > 0) {
      mcpClient
        .trackPrune(state.sessionId, state.prune.toolIds, state.stats.totalPruneTokens, "automatic")
        .catch(() => {});
    }
  };
}

export function createCommandExecuteHandler(
  state: SessionState,
  logger: Logger,
  config: CuratorConfig,
  mcpClient: McpClient,
  getMessages: (sessionId: string) => Promise<WithParts[]>
) {
  return async (
    input: { command: string; sessionID: string; arguments: string },
    _output: { parts: any[] }
  ) => {
    if (!config.commands.enabled) return;
    if (input.command !== "curator") return;

    const args = (input.arguments || "").trim().split(/\s+/).filter(Boolean);
    const subcommand = args[0]?.toLowerCase() || "help";

    const messages = await getMessages(input.sessionID);

    const { handleContextCommand } = await import("./commands/context.js");
    const { handleStatsCommand } = await import("./commands/stats.js");

    let response: string;

    switch (subcommand) {
      case "context":
        response = await handleContextCommand({ state, logger, messages });
        break;
      case "stats":
        response = await handleStatsCommand({ state, logger, mcpClient });
        break;
      default:
        response = `
## Context Curator Commands

- **/curator context** - Show token usage breakdown
- **/curator stats** - Show cumulative pruning statistics
        `.trim();
    }

    throw new Error(`__CURATOR_HANDLED__:${response}`);
  };
}

async function checkSession(
  client: any,
  state: SessionState,
  logger: Logger,
  messages: WithParts[]
): Promise<void> {
  const lastUserMessage = getLastUserMessage(messages);
  if (!lastUserMessage) return;

  const lastSessionId = lastUserMessage.info.sessionID;

  if (state.sessionId === null || state.sessionId !== lastSessionId) {
    logger.debugLog(`Session changed: ${state.sessionId} -> ${lastSessionId}`);

    resetSessionState(state);
    state.sessionId = lastSessionId;

    const isSubAgent = await isSubAgentSession(client, lastSessionId);
    state.isSubAgent = isSubAgent;

    logger.debugLog(`Session initialized`, { sessionId: lastSessionId, isSubAgent });
  }

  const lastCompactionTimestamp = findLastCompactionTimestamp(messages);
  if (lastCompactionTimestamp > state.lastCompaction) {
    state.lastCompaction = lastCompactionTimestamp;
    state.toolParameters.clear();
    state.prune.toolIds = [];
    state.extracts.summaries.clear();
    logger.debugLog("Detected compaction - cleared caches");
  }

  state.currentTurn = countTurns(state, messages);
}
