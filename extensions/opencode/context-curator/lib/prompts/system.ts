export const SYSTEM_PROMPT_BOTH = `
## Context Management

You have access to context management tools to optimize token usage:

- **discard**: Remove tool outputs that are no longer needed
- **extract**: Summarize important information before removing tool output

When you see <prunable-tools>, these are tool outputs you can manage. Use these tools when:
- Tool output has been fully processed and won't be referenced again
- You need to free up context space for new work
- Important information should be preserved as a summary

Be proactive about context management in long conversations.
`.trim();

export const SYSTEM_PROMPT_DISCARD = `
## Context Management

You have access to the **discard** tool to remove tool outputs that are no longer needed.

When you see <prunable-tools>, these are tool outputs you can discard. Use this tool when:
- Tool output has been fully processed and won't be referenced again
- You need to free up context space for new work

Be proactive about discarding unneeded context in long conversations.
`.trim();

export const SYSTEM_PROMPT_EXTRACT = `
## Context Management

You have access to the **extract** tool to summarize and remove tool outputs.

When you see <prunable-tools>, these are tool outputs you can extract from. Use this tool when:
- Important information should be preserved as a summary
- The full output is no longer needed but key insights are valuable

Be proactive about extracting and summarizing in long conversations.
`.trim();

export function getSystemPrompt(discardEnabled: boolean, extractEnabled: boolean): string | null {
  if (discardEnabled && extractEnabled) {
    return SYSTEM_PROMPT_BOTH;
  }
  if (discardEnabled) {
    return SYSTEM_PROMPT_DISCARD;
  }
  if (extractEnabled) {
    return SYSTEM_PROMPT_EXTRACT;
  }
  return null;
}
