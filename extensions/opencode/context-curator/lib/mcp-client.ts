import type { Logger } from "./logger.js";

/**
 * Statistics returned by MCP server
 */
export interface CuratorStats {
  sessionId: string;
  totalTokensSaved: number;
  pruneEvents: number;
  extractEvents: number;
  byStrategy: Record<string, number>;
}

/**
 * MCP client for communicating with spellbook server
 */
export interface McpClient {
  trackPrune(
    sessionId: string,
    toolIds: string[],
    tokensSaved: number,
    strategy: string
  ): Promise<void>;
  
  getStats(sessionId: string): Promise<CuratorStats | null>;
}

/**
 * Create MCP client with graceful degradation
 */
export function createMcpClient(port: number, logger: Logger): McpClient {
  const baseUrl = `http://localhost:${port}`;
  const timeout = 1000;
  
  async function fetchWithTimeout(
    url: string,
    options: RequestInit
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }
  
  return {
    async trackPrune(sessionId, toolIds, tokensSaved, strategy) {
      try {
        await fetchWithTimeout(`${baseUrl}/tool/mcp_curator_track_prune`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            tool_ids: toolIds,
            tokens_saved: tokensSaved,
            strategy,
          }),
        });
        logger.debugLog("MCP track prune success", { sessionId, strategy, tokensSaved });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        logger.warn(`MCP tracking failed (continuing without analytics): ${message}`, { error });
      }
    },
    
    async getStats(sessionId) {
      try {
        const response = await fetchWithTimeout(`${baseUrl}/tool/mcp_curator_get_stats`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        });
        
        if (!response.ok) {
          logger.warn(`MCP stats request failed: ${response.statusText}`, { status: response.status });
          return null;
        }
        
        const data = await response.json();
        return data as CuratorStats;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        logger.warn(`MCP stats failed (continuing without): ${message}`, { error });
        return null;
      }
    },
  };
}
