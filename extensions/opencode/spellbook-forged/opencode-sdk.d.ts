/**
 * Type declarations for @opencode-ai/sdk
 *
 * These are stub types based on the SDK reference in the Forged design document.
 * When the actual SDK is installed, these will be superseded.
 */

/**
 * Global console interface for logging.
 * This is a minimal stub for compilation without @types/node.
 */
declare const console: {
  log(...args: unknown[]): void;
  error(...args: unknown[]): void;
  warn(...args: unknown[]): void;
  info(...args: unknown[]): void;
};

declare module '@opencode-ai/sdk' {
  /**
   * Project information provided to plugins.
   */
  export interface ProjectInfo {
    name: string;
    path: string;
  }

  /**
   * Bun shell API for executing commands.
   */
  export interface BunShellAPI {
    (strings: TemplateStringsArray, ...values: unknown[]): Promise<{
      stdout: string;
      stderr: string;
      exitCode: number;
    }>;
  }

  /**
   * OpenCode SDK client for calling tools and interacting with the platform.
   */
  export interface OpenCodeSDKClient {
    /**
     * Call an MCP tool by name with arguments.
     */
    callTool(toolName: string, args?: Record<string, unknown>): Promise<unknown>;

    /**
     * Inject context into compaction summary.
     */
    injectCompactionContext(source: string, content: string): Promise<void>;
  }

  /**
   * Context provided to plugin functions.
   */
  export interface PluginContext {
    /** Project information */
    project: ProjectInfo;
    /** Current working directory */
    directory: string;
    /** Git worktree path */
    worktree: string;
    /** SDK client for platform interaction */
    client: OpenCodeSDKClient;
    /** Bun shell API */
    $: BunShellAPI;
  }

  /**
   * Plugin hooks that can be implemented.
   */
  export interface PluginHooks {
    /** Called when a session is created */
    'session.created'?: () => Promise<void>;
    /** Called when the session becomes idle */
    'session.idle'?: () => Promise<void>;
    /** Called when session context is being compacted */
    'session.compacting'?: () => Promise<void>;
    /** Called after a tool execution completes */
    'tool.execute.after'?: (toolName: string, result: unknown) => Promise<void>;
    /** Called before a tool execution starts */
    'tool.execute.before'?: (toolName: string, args: unknown) => Promise<void>;
    /** Called when a message is received */
    'message.received'?: (message: unknown) => Promise<void>;
    /** Called when a response is generated */
    'response.generated'?: (response: unknown) => Promise<void>;
  }
}
