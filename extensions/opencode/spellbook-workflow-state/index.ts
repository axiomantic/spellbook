/**
 * Spellbook Workflow State Plugin
 * 
 * Provides lifecycle hooks for workflow state persistence and recovery
 * across context compaction in OpenCode.
 */

import type { Plugin } from '@opencode-ai/plugin';
import { createPluginState, initializeWorkflowState } from './lib/state.js';
import { createMcpClient } from './lib/mcp-client.js';
import {
  createSessionCreatedHandler,
  createToolExecuteAfterHandler,
  createSessionCompactingHandler,
  createSystemPromptHandler,
} from './lib/hooks.js';

const DEFAULT_MCP_PORT = 8765;

const plugin: Plugin = async (ctx) => {
  const state = createPluginState();
  const mcpClient = createMcpClient(DEFAULT_MCP_PORT);
  
  const getProjectPath = () => ctx.directory;
  
  console.log('[workflow-state] Plugin initialized');
  
  return {
    'session.created': createSessionCreatedHandler(state, mcpClient, getProjectPath),
    
    // Hook signature: (input: { tool, sessionID, callID }, output: { title, output, metadata })
    'tool.execute.after': async (
      input: { tool: string; sessionID: string; callID: string },
      output: { title: string; output: string; metadata: any }
    ) => {
      // Initialize tracking on first tool if not already
      if (!state.isTracking && !state.workflowState) {
        state.workflowState = initializeWorkflowState(ctx.directory, 'session-' + Date.now());
        state.isTracking = true;
      }
      
      const handler = createToolExecuteAfterHandler(state, mcpClient, getProjectPath);
      // Extract tool name and pass metadata as args
      await handler(input.tool, output.metadata, output);
    },
    
    'session.compacting': createSessionCompactingHandler(
      state,
      mcpClient,
      getProjectPath,
      async (_source, _content) => {
        // Note: injectCompactionContext may not be available in all SDK versions
        // The recovery context is still saved to MCP and can be retrieved on resume
      }
    ),
    
    'experimental.chat.system.transform': createSystemPromptHandler(state, mcpClient),
  };
};

export default plugin;
