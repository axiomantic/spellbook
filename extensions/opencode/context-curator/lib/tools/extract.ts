import type { CuratorConfig } from "../types.js";
import type { Logger } from "../logger.js";
import type { SessionState } from "../types.js";
import type { McpClient } from "../mcp-client.js";

export interface ExtractToolInput {
  tool_id: string;
  summary: string;
}

export interface ExtractToolOutput {
  success: boolean;
  message: string;
}

export function createExtractTool(deps: {
  state: SessionState;
  config: CuratorConfig;
  logger: Logger;
  mcpClient: McpClient;
}) {
  const { state, config, logger, mcpClient } = deps;
  
  return {
    name: "extract",
    description: "Summarize important information from a tool output before removing it.",
    parameters: {
      type: "object",
      properties: {
        tool_id: {
          type: "string",
          description: "The tool invocation ID to extract from.",
        },
        summary: {
          type: "string",
          description: "A concise summary of the important information.",
        },
      },
      required: ["tool_id", "summary"],
    },
    
    async execute(input: ExtractToolInput): Promise<ExtractToolOutput> {
      const { tool_id, summary } = input;
      
      if (!tool_id || typeof tool_id !== "string") {
        return { success: false, message: "Invalid tool_id provided" };
      }
      
      if (!summary || typeof summary !== "string" || summary.trim().length === 0) {
        return { success: false, message: "Summary cannot be empty" };
      }
      
      if (!state.toolParameters.has(tool_id)) {
        return { success: false, message: `Tool ID "${tool_id}" not found.` };
      }
      
      state.extracts.summaries.set(tool_id, summary.trim());
      
      if (!state.prune.toolIds.includes(tool_id)) {
        state.prune.toolIds.push(tool_id);
        state.stats.prunesByStrategy["extract"] = 
          (state.stats.prunesByStrategy["extract"] || 0) + 1;
      }
      
      if (state.sessionId) {
        mcpClient.trackPrune(state.sessionId, [tool_id], 0, "extract").catch(() => {});
      }
      
      logger.debugLog(`Extract tool stored summary for ${tool_id}`);
      
      return {
        success: true,
        message: `Extracted and stored summary for tool ${tool_id}.`,
      };
    },
  };
}
