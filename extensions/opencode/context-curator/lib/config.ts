import { z } from "zod";
import type { CuratorConfig } from "./types.js";

const ConfigSchema = z.object({
  enabled: z.boolean().default(true),
  debug: z.boolean().default(false),
  mcpPort: z.number().default(8765),
  
  strategies: z.object({
    deduplication: z.object({
      enabled: z.boolean().default(true),
      protectedTools: z.array(z.string()).default([]),
    }).default({ enabled: true, protectedTools: [] }),
    supersedeWrites: z.object({
      enabled: z.boolean().default(true),
    }).default({ enabled: true }),
    purgeErrors: z.object({
      enabled: z.boolean().default(true),
      turnThreshold: z.number().default(3),
    }).default({ enabled: true, turnThreshold: 3 }),
  }).default({
    deduplication: { enabled: true, protectedTools: [] },
    supersedeWrites: { enabled: true },
    purgeErrors: { enabled: true, turnThreshold: 3 },
  }),
  
  tools: z.object({
    discard: z.object({ enabled: z.boolean().default(true) }).default({ enabled: true }),
    extract: z.object({ enabled: z.boolean().default(true) }).default({ enabled: true }),
  }).default({
    discard: { enabled: true },
    extract: { enabled: true },
  }),
  
  commands: z.object({ enabled: z.boolean().default(true) }).default({ enabled: true }),
  
  protectedFilePatterns: z.array(z.string()).default([
    "**/CLAUDE.md",
    "**/AGENTS.md",
    "**/.env*",
  ]),
});

/**
 * Load configuration from environment variables and optional overrides
 */
export function getConfig(overrides?: Record<string, unknown>): CuratorConfig {
  const envPort = process.env["SPELLBOOK_MCP_PORT"];
  const envDebug = process.env["CURATOR_DEBUG"];
  
  const rawConfig = {
    ...overrides,
    mcpPort: envPort ? parseInt(envPort, 10) : overrides?.["mcpPort"],
    debug: envDebug === "true" || overrides?.["debug"],
  };
  
  const result = ConfigSchema.safeParse(rawConfig);
  
  if (!result.success) {
    console.warn("[context-curator] Invalid config, using defaults:", result.error.message);
    return ConfigSchema.parse({});
  }
  
  return result.data;
}
