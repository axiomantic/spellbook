import type { SessionState, WithParts } from "../types.js";

export function getLastUserMessage(messages: WithParts[]): WithParts | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg?.info.role === "user") {
      return msg;
    }
  }
  return null;
}

export function isMessageCompacted(state: SessionState, msg: WithParts): boolean {
  return msg.info.time.created <= state.lastCompaction;
}
