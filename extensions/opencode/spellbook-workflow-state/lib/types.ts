/**
 * Workflow state types matching handoff.md Section 1.20 schema.
 */

export interface SkillStackEntry {
  name: string;
  parent: string | null;
  phase: string | null;
  step: string | null;
  iteration: number;
  resume_command: string;
  constraints: {
    forbidden: string[];
    required: string[];
  };
}

export interface SubagentState {
  id: string;
  persona: string;
  prompt_summary: string;
  task: string;
  status: 'pending' | 'running' | 'completed' | 'blocked' | 'failed';
  worktree: string | null;
  output_summary: string | null;
  blockers: string[];
  skill_stack: SkillStackEntry[];
}

export interface TodoItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  priority: 'high' | 'medium' | 'low';
  verification: string | null;
  delegated_to: string | null;
}

export interface WorkflowState {
  meta: {
    format_version: string;
    mode: 'manual' | 'auto' | 'checkpoint';
    project_path: string;
    project_encoded: string;
    session_id: string;
    timestamp: string;
    compaction_count: number;
  };
  identity: {
    persona: string | null;
    mode: 'fun' | 'tarot' | 'none';
    mode_context: {
      persona?: string;
      context?: string;
      undertow?: string;
    } | null;
    role: 'orchestrator' | 'executor' | 'hybrid';
  };
  skill_stack: SkillStackEntry[];
  subagents: SubagentState[];
  workflow: {
    pattern: string;
    details: string;
    waiting_for: string[];
  };
  goals: {
    ultimate: string;
    current_phase: string;
    main_task: string;
    delegated_summary: string;
  };
  todos: {
    explicit: TodoItem[];
    implicit: string[];
    blockers: string[];
  };
  documents: {
    design: Array<{ path: string; status: string; focus_sections: string[] }>;
    impl: Array<{ path: string; status: string; current_position: string; focus_sections: string[] }>;
    must_read: Array<{ path: string; why: string; priority: number }>;
  };
  decisions: {
    binding: Array<{ decision: string; rationale: string; binding: 'ABSOLUTE' | 'SESSION' }>;
    technical: Array<{ decision: string; rationale: string }>;
  };
  conversation: {
    user_messages: Array<{ content: string; type: string; timestamp: string }>;
    corrections: Array<{ original: string; correction: string; lesson: string }>;
    errors: Array<{ error: string; fix: string; user_feedback: string | null }>;
  };
}

export interface PluginState {
  sessionId: string | null;
  workflowState: WorkflowState | null;
  isTracking: boolean;
  lastCompaction: number;
}
