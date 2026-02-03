import { test, describe, beforeEach } from "node:test";
import assert from "node:assert";
import { deduplicate } from "../lib/strategies/deduplication.js";
import { createSessionState } from "../lib/state/index.js";
import { Logger } from "../lib/logger.js";
import type { CuratorConfig, WithParts } from "../lib/types.js";

describe("deduplication strategy", () => {
  let state: ReturnType<typeof createSessionState>;
  let logger: Logger;
  let config: CuratorConfig;
  
  beforeEach(() => {
    state = createSessionState();
    logger = new Logger(false);
    config = {
      enabled: true,
      debug: false,
      mcpPort: 8765,
      strategies: {
        deduplication: { enabled: true, protectedTools: [] },
        supersedeWrites: { enabled: true },
        purgeErrors: { enabled: true, turnThreshold: 3 },
      },
      tools: { discard: { enabled: true }, extract: { enabled: true } },
      commands: { enabled: true },
      protectedFilePatterns: [],
    };
  });
  
  test("marks older duplicate tool calls for pruning", () => {
    state.toolParameters.set("tool-1", {
      tool: "read",
      parameters: { file_path: "/test.txt" },
      turn: 1,
      timestamp: 1000,
    });
    state.toolParameters.set("tool-2", {
      tool: "read",
      parameters: { file_path: "/test.txt" },
      turn: 2,
      timestamp: 2000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "tool-1" },
          { type: "tool", callID: "tool-2" },
        ] as any,
      },
    ];
    
    deduplicate(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, ["tool-1"]);
  });
  
  test("keeps tools with different parameters", () => {
    state.toolParameters.set("tool-1", {
      tool: "read",
      parameters: { file_path: "/a.txt" },
      turn: 1,
      timestamp: 1000,
    });
    state.toolParameters.set("tool-2", {
      tool: "read",
      parameters: { file_path: "/b.txt" },
      turn: 2,
      timestamp: 2000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "tool-1" },
          { type: "tool", callID: "tool-2" },
        ] as any,
      },
    ];
    
    deduplicate(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, []);
  });
  
  test("skips protected tools", () => {
    config.strategies.deduplication.protectedTools = ["read"];
    
    state.toolParameters.set("tool-1", {
      tool: "read",
      parameters: { file_path: "/test.txt" },
      turn: 1,
      timestamp: 1000,
    });
    state.toolParameters.set("tool-2", {
      tool: "read",
      parameters: { file_path: "/test.txt" },
      turn: 2,
      timestamp: 2000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "tool-1" },
          { type: "tool", callID: "tool-2" },
        ] as any,
      },
    ];
    
    deduplicate(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, []);
  });
});
