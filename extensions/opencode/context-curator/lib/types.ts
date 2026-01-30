import type { Message, Part } from "@opencode-ai/sdk/v2";

/**
 * Message with parts array for processing
 */
export interface WithParts {
  info: Message;
  parts: Part[];
}

/**
 * Tool call status
 */
export type ToolStatus = "pending" | "running" | "completed" | "error";

/**
 * Tracked tool call metadata
 */
export interface ToolParameterEntry {
  tool: string;
  parameters: Record<string, unknown>;
  status?: ToolStatus;
  error?: string;
  turn: number;
  timestamp: number;
}

/**
 * Session statistics
 */
export interface SessionStats {
  pruneTokenCounter: number;
  totalPruneTokens: number;
  prunesByStrategy: Record<string, number>;
}

/**
 * Pruning state
 */
export interface PruneState {
  toolIds: string[];
}

/**
 * Extract summaries
 */
export interface ExtractState {
  summaries: Map<string, string>;
}

/**
 * Full session state
 */
export interface SessionState {
  schemaVersion: number;
  sessionId: string | null;
  isSubAgent: boolean;
  prune: PruneState;
  extracts: ExtractState;
  stats: SessionStats;
  toolParameters: Map<string, ToolParameterEntry>;
  lastCompaction: number;
  currentTurn: number;
  variant: string | undefined;
}

/**
 * Plugin configuration
 */
export interface CuratorConfig {
  enabled: boolean;
  debug: boolean;
  mcpPort: number;
  
  strategies: {
    deduplication: {
      enabled: boolean;
      protectedTools: string[];
    };
    supersedeWrites: {
      enabled: boolean;
    };
    purgeErrors: {
      enabled: boolean;
      turnThreshold: number;
    };
  };
  
  tools: {
    discard: { enabled: boolean };
    extract: { enabled: boolean };
  };
  
  commands: { enabled: boolean };
  
  protectedFilePatterns: string[];
}
