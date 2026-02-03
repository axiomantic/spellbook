import { test, describe, beforeEach } from "node:test";
import assert from "node:assert";
import { supersedeWrites } from "../lib/strategies/supersede-writes.js";
import { createSessionState } from "../lib/state/index.js";
import { Logger } from "../lib/logger.js";
import type { CuratorConfig, WithParts } from "../lib/types.js";

describe("supersede-writes strategy", () => {
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
  
  test("prunes write when followed by read of same file", () => {
    state.toolParameters.set("write-1", {
      tool: "write",
      parameters: { file_path: "/test.txt" },
      turn: 1,
      timestamp: 1000,
    });
    state.toolParameters.set("read-1", {
      tool: "read",
      parameters: { file_path: "/test.txt" },
      turn: 2,
      timestamp: 2000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "write-1" },
          { type: "tool", callID: "read-1" },
        ] as any,
      },
    ];
    
    supersedeWrites(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, ["write-1"]);
  });
  
  test("keeps write when no subsequent read", () => {
    state.toolParameters.set("write-1", {
      tool: "write",
      parameters: { file_path: "/test.txt" },
      turn: 1,
      timestamp: 1000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "write-1" },
        ] as any,
      },
    ];
    
    supersedeWrites(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, []);
  });
  
  test("keeps write when read is for different file", () => {
    state.toolParameters.set("write-1", {
      tool: "write",
      parameters: { file_path: "/a.txt" },
      turn: 1,
      timestamp: 1000,
    });
    state.toolParameters.set("read-1", {
      tool: "read",
      parameters: { file_path: "/b.txt" },
      turn: 2,
      timestamp: 2000,
    });
    
    const messages: WithParts[] = [
      {
        info: { role: "assistant", time: { created: 1500 }, sessionID: "s1" } as any,
        parts: [
          { type: "tool", callID: "write-1" },
          { type: "tool", callID: "read-1" },
        ] as any,
      },
    ];
    
    supersedeWrites(state, logger, config, messages);
    
    assert.deepStrictEqual(state.prune.toolIds, []);
  });
});
