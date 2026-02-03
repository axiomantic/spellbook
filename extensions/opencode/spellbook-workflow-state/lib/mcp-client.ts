/**
 * MCP client for calling spellbook workflow state tools.
 */

export interface McpClient {
  workflowStateSave(projectPath: string, state: object, trigger: string): Promise<any>;
  workflowStateLoad(projectPath: string, maxAgeHours?: number): Promise<any>;
  workflowStateUpdate(projectPath: string, updates: object): Promise<any>;
  skillInstructionsGet(skillName: string, sections?: string[]): Promise<any>;
}

export function createMcpClient(port: number): McpClient {
  const baseUrl = `http://127.0.0.1:${port}`;

  async function callTool(name: string, args: object): Promise<any> {
    try {
      const response = await fetch(`${baseUrl}/mcp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: name, arguments: args }),
      });
      if (!response.ok) {
        throw new Error(`MCP call failed: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`[workflow-state] MCP call ${name} failed:`, error);
      return null;
    }
  }

  return {
    workflowStateSave: (projectPath, state, trigger) =>
      callTool('workflow_state_save', { project_path: projectPath, state, trigger }),
    workflowStateLoad: (projectPath, maxAgeHours = 24.0) =>
      callTool('workflow_state_load', { project_path: projectPath, max_age_hours: maxAgeHours }),
    workflowStateUpdate: (projectPath, updates) =>
      callTool('workflow_state_update', { project_path: projectPath, updates }),
    skillInstructionsGet: (skillName, sections) =>
      callTool('skill_instructions_get', { skill_name: skillName, sections }),
  };
}
