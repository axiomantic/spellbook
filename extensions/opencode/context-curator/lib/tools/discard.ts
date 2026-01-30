import type { CuratorConfig } from "../types.js";
import type { Logger } from "../logger.js";
import type { SessionState } from "../types.js";
import type { McpClient } from "../mcp-client.js";

export interface DiscardToolInput {
  tool_ids: string[];
}

export interface DiscardToolOutput {
  success: boolean;
  discarded: number;
  invalid: string[];
  message: string;
}

export function createDiscardTool(deps: {
  state: SessionState;
  config: CuratorConfig;
  logger: Logger;
  mcpClient: McpClient;
}) {
  const { state, config, logger, mcpClient } = deps;

  return {
    name: "discard",
    description:
      "Remove tool outputs that are no longer needed to free up context space.",
    parameters: {
      type: "object",
      properties: {
        tool_ids: {
          type: "array",
          items: { type: "string" },
          description: "Array of tool invocation IDs to discard.",
        },
      },
      required: ["tool_ids"],
    },

    async execute(input: DiscardToolInput): Promise<DiscardToolOutput> {
      const { tool_ids } = input;

      if (!Array.isArray(tool_ids) || tool_ids.length === 0) {
        return {
          success: false,
          discarded: 0,
          invalid: [],
          message: "No tool IDs provided",
        };
      }

      const validIds: string[] = [];
      const invalidIds: string[] = [];

      for (const id of tool_ids) {
        if (state.toolParameters.has(id)) {
          validIds.push(id);
        } else {
          invalidIds.push(id);
        }
      }

      if (validIds.length === 0) {
        return {
          success: false,
          discarded: 0,
          invalid: invalidIds,
          message: `None of the provided IDs are valid. Invalid: ${invalidIds.join(", ")}`,
        };
      }

      const alreadyPruned = new Set(state.prune.toolIds);
      const newPruneIds = validIds.filter((id) => !alreadyPruned.has(id));

      if (newPruneIds.length > 0) {
        state.prune.toolIds.push(...newPruneIds);
        // Add to pending list for token calculation in message transform handler
        state.prune.pendingTokenCalc.push(...newPruneIds);
        state.stats.prunesByStrategy["discard"] =
          (state.stats.prunesByStrategy["discard"] || 0) + newPruneIds.length;

        logger.debugLog(
          `Discard tool marked ${newPruneIds.length} tools for pruning`,
        );
      }

      const message =
        invalidIds.length > 0
          ? `Discarded ${newPruneIds.length} tool outputs. Invalid IDs ignored: ${invalidIds.join(", ")}`
          : `Successfully discarded ${newPruneIds.length} tool outputs.`;

      return {
        success: true,
        discarded: newPruneIds.length,
        invalid: invalidIds,
        message,
      };
    },
  };
}
