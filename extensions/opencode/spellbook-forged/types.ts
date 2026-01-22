/**
 * Type definitions for the Spellbook Forged OpenCode plugin.
 *
 * These types mirror the Python dataclasses in spellbook_mcp/forged/models.py
 * and spellbook_mcp/forged/project_graph.py to ensure consistent data structures
 * across the TypeScript plugin and Python MCP server.
 */

/**
 * Valid workflow stages in the Forged autonomous development system.
 *
 * Stage Flow:
 *   IDLE -> DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE
 *                ^                           |
 *                |_______ (feedback) ________|
 *
 *   ESCALATED: Terminal state for unresolvable issues requiring human intervention.
 */
export type ForgeStage =
  | 'IDLE'
  | 'DISCOVER'
  | 'DESIGN'
  | 'PLAN'
  | 'IMPLEMENT'
  | 'COMPLETE'
  | 'ESCALATED';

/**
 * Current state of the Forged workflow for a feature.
 *
 * This is a simplified view of the iteration state, suitable for
 * UI display and plugin lifecycle hooks.
 */
export interface ForgeState {
  /** Name of the feature being developed */
  feature_name: string;
  /** Current workflow stage */
  stage: ForgeStage;
  /** Current iteration number (1-indexed) */
  iteration: number;
  /** Workflow token for the current stage, null if not in active workflow */
  token: string | null;
  /** Result of last roundtable consensus, null if not yet validated */
  last_consensus: boolean | null;
}

/**
 * A single feature in the project dependency graph.
 *
 * Represents a unit of work with dependencies on other features,
 * status tracking, and artifact associations.
 */
export interface FeatureNode {
  /** Unique identifier for the feature */
  id: string;
  /** Human-readable feature name */
  name: string;
  /** Detailed description of the feature */
  description: string;
  /** List of feature IDs this feature depends on */
  depends_on: string[];
  /** Current status of the feature */
  status: 'pending' | 'in_progress' | 'complete' | 'blocked';
  /** Complexity estimate for planning purposes */
  estimated_complexity: 'trivial' | 'small' | 'medium' | 'large' | 'epic';
  /** Currently assigned skill for this feature, null if not assigned */
  assigned_skill: string | null;
  /** List of artifact paths produced for this feature */
  artifacts: string[];
}

/**
 * Dependency graph for all features in a project.
 *
 * Manages the complete set of features, their dependency relationships,
 * and tracking of project progress.
 */
export interface ProjectGraph {
  /** Human-readable project name */
  project_name: string;
  /** Dictionary mapping feature ID to FeatureNode */
  features: Record<string, FeatureNode>;
  /** Topologically sorted list of feature IDs (dependencies first) */
  dependency_order: string[];
  /** ID of the currently active feature, null if none active */
  current_feature: string | null;
  /** List of completed feature IDs */
  completed_features: string[];
}

/**
 * Validator feedback for an artifact.
 *
 * Represents structured feedback from a validator about work product quality,
 * including the severity level and suggested resolution path.
 */
export interface Feedback {
  /** Identifier of the validator that generated this feedback */
  source: string;
  /** The workflow stage where the feedback was generated */
  stage: ForgeStage;
  /** The stage to return to for resolution */
  return_to: ForgeStage;
  /** Human-readable description of the issue */
  critique: string;
  /** Specific evidence supporting the critique */
  evidence: string;
  /** Recommended action to resolve the issue */
  suggestion: string;
  /** Impact level of the feedback */
  severity: 'blocking' | 'significant' | 'minor';
  /** The iteration number when this feedback was generated */
  iteration: number;
}

/**
 * Result from a validator execution.
 *
 * Represents the outcome of running a validator against an artifact,
 * including the verdict, any feedback, and transformation information.
 */
export interface ValidatorResult {
  /** Verdict from the validator */
  verdict: 'APPROVED' | 'FEEDBACK' | 'ABSTAIN' | 'ERROR';
  /** Feedback object if verdict is FEEDBACK, null otherwise */
  feedback: Feedback | null;
  /** Whether the validator transformed the artifact */
  transformed: boolean;
  /** Path to the validated artifact */
  artifact_path: string;
  /** Hash of the artifact for change detection */
  artifact_hash: string;
  /** Description of any transformation applied */
  transform_description: string | null;
  /** Error message if verdict is ERROR */
  error: string | null;
}

/**
 * State tracking for a single feature's development iteration.
 *
 * Represents the accumulated state across iterations of developing a feature,
 * including feedback history, learned knowledge, and user preferences.
 */
export interface IterationState {
  /** Current iteration count (1-indexed) */
  iteration_number: number;
  /** Current workflow stage */
  current_stage: ForgeStage;
  /** List of all feedback received across iterations */
  feedback_history: Feedback[];
  /** Knowledge accumulated during development */
  accumulated_knowledge: Record<string, unknown>;
  /** List of artifact paths produced */
  artifacts_produced: string[];
  /** User preferences learned during development */
  preferences: Record<string, unknown>;
  /** ISO timestamp when iteration started */
  started_at: string;
}

/**
 * Record of a skill invocation for cross-skill context persistence.
 *
 * Tracks when skills are invoked, their results, and context passed
 * between skills to enable coherent multi-skill workflows.
 */
export interface SkillInvocation {
  /** Unique identifier for this invocation */
  id: string;
  /** ID of the feature being worked on */
  feature_id: string;
  /** Name of the invoked skill */
  skill_name: string;
  /** Workflow stage when skill was invoked */
  stage: ForgeStage;
  /** Iteration number within the feature development */
  iteration: number;
  /** ISO timestamp when skill invocation started */
  started_at: string;
  /** ISO timestamp when skill invocation completed (if done) */
  completed_at: string | null;
  /** Result status (success, failure, etc.) */
  result: string | null;
  /** Context data passed to the skill */
  context_passed: Record<string, unknown>;
  /** Context data returned by the skill */
  context_returned: Record<string, unknown>;
}

/**
 * Progress information for a project.
 */
export interface ProjectProgress {
  /** Total number of features in the project */
  total_features: number;
  /** Number of completed features */
  completed_features: number;
  /** Completion percentage (0-100) */
  completion_percentage: number;
}

/**
 * Response from forge_project_status MCP tool.
 */
export interface ProjectStatusResponse {
  success: boolean;
  graph?: ProjectGraph;
  progress?: ProjectProgress;
  error?: string;
}

/**
 * Response from forge_iteration_start MCP tool.
 */
export interface IterationStartResponse {
  status: 'started' | 'resumed' | 'error';
  feature_name?: string;
  current_stage?: ForgeStage;
  iteration_number?: number;
  token?: string;
  accumulated_knowledge?: Record<string, unknown>;
  feedback_history?: Feedback[];
  error?: string;
}

/**
 * Token usage tracking for budget monitoring.
 */
export interface TokenUsage {
  /** Tool name that consumed tokens */
  tool_name: string;
  /** Number of input tokens consumed */
  input_tokens: number;
  /** Number of output tokens generated */
  output_tokens: number;
  /** Total tokens (input + output) */
  total_tokens: number;
  /** ISO timestamp of the usage */
  timestamp: string;
  /** Feature being worked on, if any */
  feature_name: string | null;
  /** Current stage, if any */
  stage: ForgeStage | null;
}

/**
 * Budget tracking state for monitoring token consumption.
 */
export interface BudgetState {
  /** Total tokens consumed in this session */
  session_tokens: number;
  /** Total tokens consumed for current feature */
  feature_tokens: number;
  /** Token usage history */
  usage_history: TokenUsage[];
  /** Session start timestamp */
  session_started_at: string;
}
