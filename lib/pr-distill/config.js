const fs = require('fs').promises;
const path = require('path');
const os = require('os');

/**
 * Base directory for PR distillation config.
 * Config is stored per-project: ~/.local/spellbook/docs/<project-encoded>/pr-distill-config.json
 */
const CONFIG_DIR = path.join(os.homedir(), '.local', 'spellbook', 'docs');

/**
 * Default configuration values.
 * @type {{
 *   blessed_patterns: string[],
 *   always_review_paths: string[],
 *   query_count_thresholds: { relative_percent: number, absolute_delta: number }
 * }}
 */
const DEFAULT_CONFIG = {
  blessed_patterns: [],
  always_review_paths: [],
  query_count_thresholds: {
    relative_percent: 20,
    absolute_delta: 10,
  },
};

/**
 * Dependencies container for testing.
 */
let deps = {
  readFile: fs.readFile.bind(fs),
  writeFile: fs.writeFile.bind(fs),
  mkdir: fs.mkdir.bind(fs),
  access: fs.access.bind(fs),
};

/**
 * Set custom dependencies for testing.
 * @param {Object} newDeps - Partial dependencies to override
 */
function setDeps(newDeps) {
  deps = { ...deps, ...newDeps };
}

/**
 * Reset dependencies to defaults.
 */
function resetDeps() {
  deps = {
    readFile: fs.readFile.bind(fs),
    writeFile: fs.writeFile.bind(fs),
    mkdir: fs.mkdir.bind(fs),
    access: fs.access.bind(fs),
  };
}

/**
 * Encode a project root path for use in filesystem.
 * Removes leading slash and replaces remaining slashes with dashes.
 * @param {string} projectRoot - Absolute path to project root
 * @returns {string} Encoded path suitable for directory name
 */
function encodeProjectPath(projectRoot) {
  // Remove leading slash and replace remaining slashes with dashes
  return projectRoot.replace(/^\//, '').replace(/\//g, '-');
}

/**
 * Get the config file path for a project.
 * @param {string} projectRoot - Absolute path to project root
 * @returns {string} Absolute path to config file
 */
function getConfigPath(projectRoot) {
  const encoded = encodeProjectPath(projectRoot);
  return path.join(CONFIG_DIR, encoded, 'pr-distill-config.json');
}

/**
 * Load configuration for a project.
 * Returns default config if file does not exist.
 * @param {string} projectRoot - Absolute path to project root
 * @returns {Promise<Object>} Configuration object
 */
async function loadConfig(projectRoot) {
  const configPath = getConfigPath(projectRoot);

  try {
    await deps.access(configPath);
  } catch {
    // File doesn't exist, return defaults
    return { ...DEFAULT_CONFIG };
  }

  try {
    const content = await deps.readFile(configPath, 'utf8');
    const loaded = JSON.parse(content);

    // Merge with defaults for any missing keys
    return {
      blessed_patterns: loaded.blessed_patterns ?? DEFAULT_CONFIG.blessed_patterns,
      always_review_paths: loaded.always_review_paths ?? DEFAULT_CONFIG.always_review_paths,
      query_count_thresholds: loaded.query_count_thresholds ?? DEFAULT_CONFIG.query_count_thresholds,
    };
  } catch {
    // Parse error or read error, return defaults
    return { ...DEFAULT_CONFIG };
  }
}

/**
 * Save configuration for a project.
 * Creates directories if they don't exist.
 * @param {string} projectRoot - Absolute path to project root
 * @param {Object} config - Configuration object to save
 * @returns {Promise<void>}
 */
async function saveConfig(projectRoot, config) {
  const configPath = getConfigPath(projectRoot);
  const configDir = path.dirname(configPath);

  // Create directory structure
  await deps.mkdir(configDir, { recursive: true });

  // Write config with pretty-printing
  await deps.writeFile(configPath, JSON.stringify(config, null, 2));
}

/**
 * Add a pattern to the blessed_patterns list.
 * Does not duplicate existing patterns.
 * @param {string} projectRoot - Absolute path to project root
 * @param {string} patternId - Pattern ID to bless
 * @returns {Promise<Object>} Updated configuration object
 */
async function blessPattern(projectRoot, patternId) {
  // Load existing config (or defaults)
  const config = await loadConfig(projectRoot);

  // Add pattern if not already present
  if (!config.blessed_patterns.includes(patternId)) {
    config.blessed_patterns.push(patternId);
  }

  // Save updated config
  await saveConfig(projectRoot, config);

  return config;
}

module.exports = {
  CONFIG_DIR,
  DEFAULT_CONFIG,
  getConfigPath,
  loadConfig,
  saveConfig,
  blessPattern,
  // For testing
  setDeps,
  resetDeps,
};
