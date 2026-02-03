import type { Logger } from "../logger.js";
import type { SessionState } from "../types.js";
import type { McpClient } from "../mcp-client.js";

export interface StatsCommandDeps {
  state: SessionState;
  logger: Logger;
  mcpClient: McpClient;
}

export async function handleStatsCommand(deps: StatsCommandDeps): Promise<string> {
  const { state, mcpClient } = deps;
  
  let mcpStats = null;
  if (state.sessionId) {
    mcpStats = await mcpClient.getStats(state.sessionId);
  }
  
  const byStrategy = Object.entries(state.stats.prunesByStrategy)
    .map(([strategy, count]) => `  - ${strategy}: ${count}`)
    .join("\n");
  
  let output = `
## Context Curator Statistics

**Session ID:** ${state.sessionId || "N/A"}
**Total Tokens Saved:** ~${state.stats.totalPruneTokens.toLocaleString()}
**Total Prunes:** ${state.prune.toolIds.length}
**Extracts Stored:** ${state.extracts.summaries.size}

**By Strategy:**
${byStrategy || "  (none yet)"}
`.trim();
  
  if (mcpStats) {
    output += `

**MCP Historical Data:**
- Total Events: ${mcpStats.pruneEvents + mcpStats.extractEvents}
- Lifetime Tokens Saved: ~${mcpStats.totalTokensSaved.toLocaleString()}
`;
  }
  
  return output;
}
