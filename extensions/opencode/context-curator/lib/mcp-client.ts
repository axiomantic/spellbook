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
        await fetchWithTimeout(`${baseUrl}/curator/track`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sessionId, toolIds, tokensSaved, strategy }),
        });
        logger.debugLog("MCP track prune success", { sessionId, strategy, tokensSaved });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        logger.warn(`MCP tracking failed (continuing without analytics): ${message}`);
      }
    },
    
    async getStats(sessionId) {
      try {
        const response = await fetchWithTimeout(`${baseUrl}/curator/stats?session_id=${sessionId}`, {
          method: "GET",
        });
        
        if (!response.ok) {
          logger.warn(`MCP stats request failed: ${response.status}`);
          return null;
        }
        
        const data = await response.json();
        return data as CuratorStats;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        logger.warn(`MCP stats failed (continuing without): ${message}`);
        return null;
      }
    },
  };
}
