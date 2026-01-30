import type { Plugin } from "@opencode-ai/plugin";

const plugin: Plugin = async (ctx) => {
  console.log("[context-curator] Plugin loaded");
  
  return {
    // Hooks will be added in subsequent tasks
  };
};

export default plugin;
