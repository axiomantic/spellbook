import type { Plugin } from "@opencode-ai/plugin";
import { getConfig } from "./lib/config.js";
import { Logger } from "./lib/logger.js";
import { createSessionState } from "./lib/state/index.js";
import { createMcpClient } from "./lib/mcp-client.js";
import { createDiscardTool, createExtractTool } from "./lib/tools/index.js";
import {
  createSystemPromptHandler,
  createChatMessageTransformHandler,
  createCommandExecuteHandler,
} from "./lib/hooks.js";
import type { WithParts } from "./lib/types.js";

const plugin: Plugin = async (ctx) => {
  const config = getConfig(ctx);
  
  if (!config.enabled) {
    console.log("[context-curator] Plugin disabled");
    return {};
  }
  
  const logger = new Logger(config.debug);
  const state = createSessionState();
  const mcpClient = createMcpClient(config.mcpPort, logger);
  
  logger.info("Context Curator initialized", {
    strategies: {
      deduplication: config.strategies.deduplication.enabled,
      supersedeWrites: config.strategies.supersedeWrites.enabled,
      purgeErrors: config.strategies.purgeErrors.enabled,
    },
    tools: {
      discard: config.tools.discard.enabled,
      extract: config.tools.extract.enabled,
    },
  });
  
  const getMessages = async (sessionId: string): Promise<WithParts[]> => {
    try {
      const response = await ctx.client.session.messages({ path: { id: sessionId } });
      return (response.data || response) as WithParts[];
    } catch (error) {
      logger.warn("Failed to fetch messages for session", { sessionId, error });
      return [];
    }
  };
  
  return {
    "experimental.chat.system.transform": createSystemPromptHandler(state, logger, config),
    
    "experimental.chat.messages.transform": createChatMessageTransformHandler(
      ctx.client,
      state,
      logger,
      config,
      mcpClient
    ),
    
    "chat.message": async (
      input: { sessionID: string; variant?: string },
      _output: any
    ) => {
      state.variant = input.variant;
      logger.debugLog("Cached variant from chat.message hook", { variant: input.variant });
    },
    
    "command.execute.before": createCommandExecuteHandler(
      state,
      logger,
      config,
      mcpClient,
      getMessages
    ),
    
    tool: {
      ...(config.tools.discard.enabled && {
        discard: createDiscardTool({ state, config, logger, mcpClient }),
      }),
      ...(config.tools.extract.enabled && {
        extract: createExtractTool({ state, config, logger, mcpClient }),
      }),
    },
    
    config: async (opencodeConfig: any) => {
      if (config.commands.enabled) {
        opencodeConfig.command ??= {};
        opencodeConfig.command["curator"] = {
          template: "",
          description: "Context Curator - manage context and view statistics",
        };
      }
      
      const toolsToAdd: string[] = [];
      if (config.tools.discard.enabled) toolsToAdd.push("discard");
      if (config.tools.extract.enabled) toolsToAdd.push("extract");
      
      if (toolsToAdd.length > 0) {
        const existingPrimaryTools = opencodeConfig.experimental?.primary_tools ?? [];
        opencodeConfig.experimental = {
          ...opencodeConfig.experimental,
          primary_tools: [...existingPrimaryTools, ...toolsToAdd],
        };
        logger.debugLog(`Added ${toolsToAdd.join(", ")} to experimental.primary_tools`);
      }
    },
  };
};

export default plugin;
