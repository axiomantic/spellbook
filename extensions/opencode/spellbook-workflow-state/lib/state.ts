/**
 * Plugin state management.
 */

import type { PluginState, WorkflowState, SkillStackEntry, SubagentState, TodoItem } from './types.js';

export function createPluginState(): PluginState {
  return {
    sessionId: null,
    workflowState: null,
    isTracking: false,
    lastCompaction: 0,
  };
}

export function resetPluginState(state: PluginState): void {
  state.sessionId = null;
  state.workflowState = null;
  state.isTracking = false;
}

export function initializeWorkflowState(projectPath: string, sessionId: string): WorkflowState {
  return {
    meta: {
      format_version: '3.0',
      mode: 'auto',
      project_path: projectPath,
      project_encoded: projectPath.replace(/^\//, '').replace(/\//g, '-'),
      session_id: sessionId,
      timestamp: new Date().toISOString(),
      compaction_count: 0,
    },
    identity: {
      persona: null,
      mode: 'none',
      mode_context: null,
      role: 'hybrid',
    },
    skill_stack: [],
    subagents: [],
    workflow: {
      pattern: 'single-threaded',
      details: '',
      waiting_for: [],
    },
    goals: {
      ultimate: '',
      current_phase: '',
      main_task: '',
      delegated_summary: '',
    },
    todos: {
      explicit: [],
      implicit: [],
      blockers: [],
    },
    documents: {
      design: [],
      impl: [],
      must_read: [],
    },
    decisions: {
      binding: [],
      technical: [],
    },
    conversation: {
      user_messages: [],
      corrections: [],
      errors: [],
    },
  };
}
