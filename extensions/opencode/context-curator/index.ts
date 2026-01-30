import type { Plugin } from "@opencode-ai/plugin";
import { getConfig } from "./lib/config.js";

const plugin: Plugin = async (_ctx) => {
  const config = getConfig();
  
  if (!config.enabled) {
    console.log("[context-curator] Plugin disabled");
    return {};
  }
  
  if (config.debug) {
    console.log("[context-curator] Config:", JSON.stringify(config, null, 2));
  }
  
  console.log("[context-curator] Plugin loaded");
  
  return {
    // Hooks will be added in subsequent tasks
  };
};

export default plugin;
