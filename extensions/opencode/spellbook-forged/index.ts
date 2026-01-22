/**
 * Spellbook Forged OpenCode Plugin
 *
 * Provides lifecycle hooks for autonomous development workflow automation
 * in the OpenCode platform. Integrates with the Spellbook MCP server to:
 *
 * - Check for in-progress features on session start
 * - Auto-convene roundtable validation when stage work completes
 * - Preserve forge state across context compaction
 * - Track token usage for budget monitoring
 *
 * @module spellbook-forged
 */

import type { PluginContext, PluginHooks } from '@opencode-ai/sdk';
import type {
  ForgeState,
  ForgeStage,
  ProjectStatusResponse,
  IterationStartResponse,
  BudgetState,
  TokenUsage,
} from './types';

/**
 * In-memory budget tracking state.
 * Persists for the duration of the plugin lifecycle.
 */
let budgetState: BudgetState = {
  session_tokens: 0,
  feature_tokens: 0,
  usage_history: [],
  session_started_at: new Date().toISOString(),
};

/**
 * Current forge state, updated by lifecycle hooks.
 */
let currentForgeState: ForgeState | null = null;

/**
 * Format a status banner for display in the session.
 *
 * @param state - Current forge state
 * @returns Formatted banner string
 */
function formatStatusBanner(state: ForgeState): string {
  const stageEmoji: Record<ForgeStage, string> = {
    IDLE: '',
    DISCOVER: '',
    DESIGN: '',
    PLAN: '',
    IMPLEMENT: '',
    COMPLETE: '',
    ESCALATED: '',
  };

  const emoji = stageEmoji[state.stage];
  const iteration = state.iteration > 1 ? ` (iteration ${state.iteration})` : '';

  return `${emoji} Forged: "${state.feature_name}" at ${state.stage}${iteration}`;
}

/**
 * Call an MCP tool via the OpenCode SDK client.
 *
 * @param client - OpenCode SDK client
 * @param toolName - Name of the MCP tool to call
 * @param args - Arguments to pass to the tool
 * @returns Tool result or null on error
 */
async function callMcpTool<T>(
  client: PluginContext['client'],
  toolName: string,
  args: Record<string, unknown> = {}
): Promise<T | null> {
  try {
    const result = await client.callTool(toolName, args);
    return result as T;
  } catch (error) {
    console.error(`[spellbook-forged] Error calling ${toolName}:`, error);
    return null;
  }
}

/**
 * Hook: session.created
 *
 * Called when a new OpenCode session starts. Checks for in-progress features
 * and displays a status banner if work is ongoing.
 *
 * @param context - Plugin context with project info and SDK client
 */
async function onSessionCreated(context: PluginContext): Promise<void> {
  const { directory, client } = context;

  // Reset budget state for new session
  budgetState = {
    session_tokens: 0,
    feature_tokens: 0,
    usage_history: [],
    session_started_at: new Date().toISOString(),
  };

  // Call forge_project_status MCP tool to check for in-progress features
  const statusResult = await callMcpTool<ProjectStatusResponse>(
    client,
    'forge_project_status',
    { project_path: directory }
  );

  if (!statusResult?.success || !statusResult.graph) {
    // No project graph found, nothing to display
    currentForgeState = null;
    return;
  }

  const { graph, progress } = statusResult;

  // Check if there's a current feature in progress
  if (graph.current_feature) {
    const feature = graph.features[graph.current_feature];
    if (feature) {
      // Get iteration state for the feature
      const iterationResult = await callMcpTool<IterationStartResponse>(
        client,
        'forge_iteration_start',
        { feature_name: feature.name }
      );

      if (iterationResult?.status === 'resumed') {
        currentForgeState = {
          feature_name: feature.name,
          stage: (iterationResult.current_stage ?? 'IDLE') as ForgeStage,
          iteration: iterationResult.iteration_number ?? 1,
          token: iterationResult.token ?? null,
          last_consensus: null,
        };

        // Display status banner
        const banner = formatStatusBanner(currentForgeState);
        console.log(`\n${banner}`);

        if (progress) {
          console.log(
            `   Project: ${progress.completed_features}/${progress.total_features} features complete (${progress.completion_percentage.toFixed(0)}%)`
          );
        }

        // Show any pending feedback from previous iteration
        if (iterationResult.feedback_history?.length) {
          const lastFeedback =
            iterationResult.feedback_history[iterationResult.feedback_history.length - 1];
          if (lastFeedback) {
            console.log(`   Last feedback: [${lastFeedback.severity}] ${lastFeedback.critique}`);
          }
        }

        console.log('');
      }
    }
  }
}

/**
 * Hook: session.idle
 *
 * Called when the session becomes idle (no active operations). Detects stage
 * completion and auto-convenes the roundtable for validation.
 *
 * @param context - Plugin context with project info and SDK client
 */
async function onSessionIdle(context: PluginContext): Promise<void> {
  const { client } = context;

  // Only proceed if we have an active forge state with a token
  if (!currentForgeState?.token) {
    return;
  }

  // Skip if we're at a terminal stage
  if (currentForgeState.stage === 'COMPLETE' || currentForgeState.stage === 'ESCALATED') {
    return;
  }

  // Check if stage work appears complete by looking for artifacts
  // This is a heuristic - the roundtable will make the final determination
  const stageArtifacts = await detectStageCompletion(context, currentForgeState.stage);

  if (!stageArtifacts.complete) {
    return;
  }

  console.log(`\n[spellbook-forged] Stage ${currentForgeState.stage} work detected complete.`);
  console.log('[spellbook-forged] Convening roundtable for validation...\n');

  // Convene the roundtable by invoking the tarot-mode validator pattern
  // This is done by calling the forge_roundtable_convene tool
  const roundtableResult = await callMcpTool<{
    verdict: 'ITERATE' | 'APPROVE' | 'ABSTAIN';
    feedback?: { critique: string; suggestion: string; severity: string }[];
    next_stage?: string;
    token?: string;
  }>(client, 'forge_roundtable_convene', {
    feature_name: currentForgeState.feature_name,
    current_token: currentForgeState.token,
    stage: currentForgeState.stage,
    artifacts: stageArtifacts.paths,
  });

  if (!roundtableResult) {
    console.log('[spellbook-forged] Roundtable convene failed, manual intervention may be needed.');
    return;
  }

  // Handle the roundtable verdict
  switch (roundtableResult.verdict) {
    case 'APPROVE':
      currentForgeState.last_consensus = true;
      if (roundtableResult.next_stage) {
        currentForgeState.stage = roundtableResult.next_stage as ForgeStage;
      }
      if (roundtableResult.token) {
        currentForgeState.token = roundtableResult.token;
      }
      console.log(`[spellbook-forged] Roundtable APPROVED. Advanced to ${currentForgeState.stage}.`);
      break;

    case 'ITERATE':
      currentForgeState.last_consensus = false;
      currentForgeState.iteration += 1;
      if (roundtableResult.token) {
        currentForgeState.token = roundtableResult.token;
      }
      console.log('[spellbook-forged] Roundtable requests ITERATION.');
      if (roundtableResult.feedback?.length) {
        const fb = roundtableResult.feedback[0];
        if (fb) {
          console.log(`   Feedback: [${fb.severity}] ${fb.critique}`);
          console.log(`   Suggestion: ${fb.suggestion}`);
        }
      }
      break;

    case 'ABSTAIN':
      console.log('[spellbook-forged] Roundtable ABSTAINED. Proceeding without validation.');
      break;
  }

  console.log('');
}

/**
 * Detect if stage work appears complete by checking for expected artifacts.
 *
 * @param context - Plugin context
 * @param stage - Current stage to check
 * @returns Object with completion status and artifact paths
 */
async function detectStageCompletion(
  context: PluginContext,
  stage: ForgeStage
): Promise<{ complete: boolean; paths: string[] }> {
  const { $ } = context;

  // Stage-specific artifact patterns
  const stagePatterns: Record<ForgeStage, string[]> = {
    IDLE: [],
    DISCOVER: ['**/discovery-*.md', '**/requirements-*.md'],
    DESIGN: ['**/design-*.md', '**/architecture-*.md'],
    PLAN: ['**/plan-*.md', '**/implementation-plan-*.md'],
    IMPLEMENT: ['**/*.ts', '**/*.py', '**/*.js'],
    COMPLETE: [],
    ESCALATED: [],
  };

  const patterns = stagePatterns[stage];
  if (patterns.length === 0) {
    return { complete: false, paths: [] };
  }

  // Use shell to find matching files (glob via find)
  const paths: string[] = [];
  for (const pattern of patterns) {
    try {
      const result = await $`find . -path "${pattern}" -type f 2>/dev/null | head -10`;
      const files = result.stdout.trim().split('\n').filter(Boolean);
      paths.push(...files);
    } catch {
      // Ignore errors from find
    }
  }

  // Simple heuristic: if we found any matching artifacts, consider it potentially complete
  return {
    complete: paths.length > 0,
    paths: paths.slice(0, 10), // Limit to first 10
  };
}

/**
 * Hook: session.compacting
 *
 * Called when the session context is being compacted (summarized to reduce size).
 * Injects forge state into the compaction summary to preserve workflow continuity.
 *
 * @param context - Plugin context with project info and SDK client
 */
async function onSessionCompacting(context: PluginContext): Promise<void> {
  const { client, directory } = context;

  // Get fresh forge state before compaction
  const statusResult = await callMcpTool<ProjectStatusResponse>(
    client,
    'forge_project_status',
    { project_path: directory }
  );

  if (!statusResult?.success || !currentForgeState) {
    return;
  }

  // Build compaction summary with forge state
  const compactionContext = {
    forged_state: {
      feature_name: currentForgeState.feature_name,
      stage: currentForgeState.stage,
      iteration: currentForgeState.iteration,
      token: currentForgeState.token,
      last_consensus: currentForgeState.last_consensus,
    },
    budget_state: {
      session_tokens: budgetState.session_tokens,
      feature_tokens: budgetState.feature_tokens,
    },
    project_progress: statusResult.progress,
  };

  // Inject into compaction summary via client
  // The client.injectCompactionContext method adds this to the summary
  try {
    await client.injectCompactionContext(
      'spellbook-forged',
      JSON.stringify(compactionContext, null, 2)
    );
    console.log('[spellbook-forged] Forge state preserved in compaction summary.');
  } catch (error) {
    console.error('[spellbook-forged] Failed to inject compaction context:', error);
  }
}

/**
 * Hook: tool.execute.after
 *
 * Called after any tool execution completes. Tracks token usage from tool calls
 * for budget monitoring.
 *
 * @param context - Plugin context
 * @param toolName - Name of the tool that was executed
 * @param result - Result from the tool execution
 */
async function onToolExecuteAfter(
  context: PluginContext,
  toolName: string,
  result: unknown
): Promise<void> {
  // Extract token usage from result if available
  // The structure depends on the tool, but many tools include usage info
  const usage = extractTokenUsage(toolName, result);

  if (usage.total_tokens > 0) {
    // Update budget tracking
    budgetState.session_tokens += usage.total_tokens;
    budgetState.feature_tokens += usage.total_tokens;
    budgetState.usage_history.push(usage);

    // Keep history limited to last 100 entries
    if (budgetState.usage_history.length > 100) {
      budgetState.usage_history = budgetState.usage_history.slice(-100);
    }

    // Log high-usage tools
    if (usage.total_tokens > 1000) {
      console.log(
        `[spellbook-forged] High token usage: ${toolName} used ${usage.total_tokens} tokens`
      );
    }
  }

  // Track tool usage in the database for analytics
  // This is done via MCP tool call to persist across sessions
  if (currentForgeState) {
    await callMcpTool(context.client, 'forge_track_tool_usage', {
      tool_name: toolName,
      project_path: context.directory,
      feature_name: currentForgeState.feature_name,
      stage: currentForgeState.stage,
      iteration: currentForgeState.iteration,
      input_tokens: usage.input_tokens,
      output_tokens: usage.output_tokens,
    });
  }
}

/**
 * Extract token usage information from a tool result.
 *
 * @param toolName - Name of the tool
 * @param result - Raw result from tool execution
 * @returns TokenUsage object
 */
function extractTokenUsage(toolName: string, result: unknown): TokenUsage {
  const now = new Date().toISOString();
  const baseUsage: TokenUsage = {
    tool_name: toolName,
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    timestamp: now,
    feature_name: currentForgeState?.feature_name ?? null,
    stage: currentForgeState?.stage ?? null,
  };

  // Handle various result formats
  if (result && typeof result === 'object') {
    const r = result as Record<string, unknown>;

    // Direct usage field
    if (r['usage'] && typeof r['usage'] === 'object') {
      const usage = r['usage'] as Record<string, unknown>;
      baseUsage.input_tokens = typeof usage['input_tokens'] === 'number' ? usage['input_tokens'] : 0;
      baseUsage.output_tokens =
        typeof usage['output_tokens'] === 'number' ? usage['output_tokens'] : 0;
    }

    // Anthropic-style usage
    if (typeof r['input_tokens'] === 'number') {
      baseUsage.input_tokens = r['input_tokens'];
    }
    if (typeof r['output_tokens'] === 'number') {
      baseUsage.output_tokens = r['output_tokens'];
    }

    // OpenAI-style usage
    if (typeof r['prompt_tokens'] === 'number') {
      baseUsage.input_tokens = r['prompt_tokens'];
    }
    if (typeof r['completion_tokens'] === 'number') {
      baseUsage.output_tokens = r['completion_tokens'];
    }
  }

  baseUsage.total_tokens = baseUsage.input_tokens + baseUsage.output_tokens;
  return baseUsage;
}

/**
 * Plugin factory function.
 *
 * Creates and returns the plugin hooks object that OpenCode will use
 * to integrate with the Forged autonomous development system.
 *
 * @param context - Plugin context provided by OpenCode
 * @returns PluginHooks object with lifecycle callbacks
 */
export default function createPlugin(context: {
  project: { name: string; path: string };
  directory: string;
  worktree: string;
  client: PluginContext['client'];
  $: PluginContext['$'];
}): PluginHooks {
  // Create plugin context wrapper
  const pluginContext: PluginContext = {
    project: context.project,
    directory: context.directory,
    worktree: context.worktree,
    client: context.client,
    $: context.$,
  };

  return {
    /**
     * Called when a new session is created.
     */
    'session.created': async () => {
      await onSessionCreated(pluginContext);
    },

    /**
     * Called when the session becomes idle.
     */
    'session.idle': async () => {
      await onSessionIdle(pluginContext);
    },

    /**
     * Called when session context is being compacted.
     */
    'session.compacting': async () => {
      await onSessionCompacting(pluginContext);
    },

    /**
     * Called after a tool execution completes.
     */
    'tool.execute.after': async (toolName: string, result: unknown) => {
      await onToolExecuteAfter(pluginContext, toolName, result);
    },
  };
}
