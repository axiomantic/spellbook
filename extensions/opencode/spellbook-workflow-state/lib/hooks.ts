/**
 * OpenCode plugin hooks for workflow state management.
 */

import type { PluginState, WorkflowState, SkillStackEntry, SubagentState } from './types.js';
import type { McpClient } from './mcp-client.js';
import { initializeWorkflowState } from './state.js';

export function createSessionCreatedHandler(
  state: PluginState,
  mcpClient: McpClient,
  getProjectPath: () => string
) {
  return async (): Promise<void> => {
    const projectPath = getProjectPath();
    
    // Check for resumable state
    const result = await mcpClient.workflowStateLoad(projectPath);
    
    if (result?.found && result?.state) {
      state.workflowState = result.state as WorkflowState;
      state.isTracking = true;
      
      console.log(`[workflow-state] Resumable workflow detected:`);
      console.log(`  Skill: ${state.workflowState.skill_stack[0]?.name || 'none'}`);
      console.log(`  Phase: ${state.workflowState.skill_stack[0]?.phase || 'none'}`);
      console.log(`  Role: ${state.workflowState.identity.role}`);
    }
  };
}

export function createToolExecuteAfterHandler(
  state: PluginState,
  mcpClient: McpClient,
  getProjectPath: () => string
) {
  return async (toolName: string, args: unknown, result: unknown): Promise<void> => {
    if (!state.isTracking || !state.workflowState) return;
    
    const updates: Partial<WorkflowState> = {};
    
    // Track Skill invocations
    if (toolName === 'Skill' || toolName === 'mcp_skill') {
      const skillArgs = args as { skill_name?: string; name?: string };
      const skillName = skillArgs?.skill_name || skillArgs?.name;
      if (skillName) {
        const entry: SkillStackEntry = {
          name: skillName,
          parent: state.workflowState.skill_stack[0]?.name || null,
          phase: null,
          step: null,
          iteration: 1,
          resume_command: `Skill("${skillName}")`,
          constraints: { forbidden: [], required: [] },
        };
        updates.skill_stack = [entry];
      }
    }
    
    // Track Task/subagent spawns
    if (toolName === 'Task' || toolName === 'mcp_task') {
      const taskArgs = args as { description?: string; prompt?: string };
      const subagent: SubagentState = {
        id: `agent-${Date.now()}`,
        persona: '',
        prompt_summary: taskArgs?.description || '',
        task: taskArgs?.prompt?.slice(0, 100) || '',
        status: 'running',
        worktree: null,
        output_summary: null,
        blockers: [],
        skill_stack: [],
      };
      updates.subagents = [subagent];
    }
    
    // Track TodoWrite
    if (toolName === 'TodoWrite' || toolName === 'mcp_todowrite') {
      const todoArgs = args as { todos?: Array<{ content: string; status: string; priority?: string }> };
      if (todoArgs?.todos) {
        updates.todos = {
          explicit: todoArgs.todos.map((t, i) => ({
            id: String(i),
            content: t.content,
            status: t.status as any,
            priority: (t.priority as any) || 'medium',
            verification: null,
            delegated_to: null,
          })),
          implicit: [],
          blockers: [],
        };
      }
    }
    
    if (Object.keys(updates).length > 0) {
      await mcpClient.workflowStateUpdate(getProjectPath(), updates);
    }
  };
}

export function createSessionCompactingHandler(
  state: PluginState,
  mcpClient: McpClient,
  getProjectPath: () => string,
  injectContext: (source: string, content: string) => Promise<void>
) {
  return async (): Promise<void> => {
    if (!state.workflowState) return;
    
    // Update compaction count
    state.workflowState.meta.compaction_count += 1;
    state.workflowState.meta.timestamp = new Date().toISOString();
    
    // Save to MCP
    await mcpClient.workflowStateSave(
      getProjectPath(),
      state.workflowState,
      'auto'
    );
    
    // Build recovery context
    const recovery = formatRecoveryContext(state.workflowState);
    await injectContext('spellbook-workflow', recovery);
    
    console.log('[workflow-state] State preserved for recovery');
  };
}

export function createSystemPromptHandler(
  state: PluginState,
  mcpClient: McpClient
) {
  return async (_input: unknown, output: { system: string[] }): Promise<void> => {
    if (!state.workflowState) return;
    
    const ws = state.workflowState;
    const topSkill = ws.skill_stack[0];
    
    // Inject role constraint
    if (ws.identity.role === 'orchestrator') {
      output.system.push(`
**ORCHESTRATOR MODE ACTIVE**
You are continuing a workflow. You delegate work to subagents. You do NOT implement directly.
`.trim());
    }
    
    // Inject skill constraints
    if (topSkill?.constraints) {
      if (topSkill.constraints.forbidden.length > 0) {
        output.system.push(`
**FORBIDDEN:**
${topSkill.constraints.forbidden.map(f => `- ${f}`).join('\n')}
`.trim());
      }
      if (topSkill.constraints.required.length > 0) {
        output.system.push(`
**REQUIRED:**
${topSkill.constraints.required.map(r => `- ${r}`).join('\n')}
`.trim());
      }
    }
  };
}

function formatRecoveryContext(ws: WorkflowState): string {
  const topSkill = ws.skill_stack[0];
  
  return `
<workflow-recovery>
## Resuming Workflow

**Skill:** ${topSkill?.name || 'none'} at ${topSkill?.phase || 'start'}
**Role:** ${ws.identity.role}
**Pattern:** ${ws.workflow.pattern}

### Execute Immediately

1. **Restore skill:**
\`\`\`
${topSkill?.resume_command || 'NO ACTIVE SKILL'}
\`\`\`

2. **Read documents:**
\`\`\`
${ws.documents.must_read.map(d => `Read("${d.path}")`).join('\n') || 'NO DOCUMENTS'}
\`\`\`

### Active Subagents
${ws.subagents.map(s => `- ${s.id}: ${s.task} (${s.status})`).join('\n') || 'None'}

### Waiting For
${ws.workflow.waiting_for.map(w => `- ${w}`).join('\n') || 'Nothing'}

### Decisions (DO NOT RE-LITIGATE)
${ws.decisions.binding.map(d => `- ${d.decision}`).join('\n') || 'None'}

### Corrections (DO NOT REPEAT)
${ws.conversation.corrections.map(c => `- ${c.lesson}`).join('\n') || 'None'}
</workflow-recovery>
`.trim();
}
