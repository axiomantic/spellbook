const configModule = require('./config.js');

/**
 * Dependencies container for testing.
 * @type {{
 *   loadConfig: Function,
 *   blessPattern: Function
 * }}
 */
let deps = {
  loadConfig: configModule.loadConfig,
  blessPattern: configModule.blessPattern,
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
    loadConfig: configModule.loadConfig,
    blessPattern: configModule.blessPattern,
  };
}

/**
 * Validate a pattern ID against naming rules.
 *
 * Rules:
 * - Length: 2-50 characters
 * - Characters: [a-z0-9-] (lowercase letters, numbers, hyphens)
 * - Must start with a letter
 * - Must end with a letter or number
 * - No double hyphens (--)
 * - Cannot start with _builtin- (reserved prefix)
 *
 * @param {string} patternId - Pattern ID to validate
 * @returns {{valid: true} | {valid: false, error: string}}
 */
function validatePatternId(patternId) {
  // Check length
  if (patternId.length < 2 || patternId.length > 50) {
    return {
      valid: false,
      error: 'Pattern ID must be 2-50 characters long',
    };
  }

  // Check reserved prefix
  if (patternId.startsWith('_builtin-')) {
    return {
      valid: false,
      error: 'Pattern ID cannot use reserved prefix "_builtin-"',
    };
  }

  // Check valid characters (lowercase letters, numbers, hyphens only)
  if (!/^[a-z0-9-]+$/.test(patternId)) {
    return {
      valid: false,
      error: 'Pattern ID must contain only lowercase letters, numbers, and hyphens',
    };
  }

  // Check starts with letter
  if (!/^[a-z]/.test(patternId)) {
    return {
      valid: false,
      error: 'Pattern ID must start with a letter',
    };
  }

  // Check ends with letter or number
  if (!/[a-z0-9]$/.test(patternId)) {
    return {
      valid: false,
      error: 'Pattern ID must end with a letter or number',
    };
  }

  // Check no double hyphens
  if (patternId.includes('--')) {
    return {
      valid: false,
      error: 'Pattern ID cannot contain double hyphen (--)',
    };
  }

  return { valid: true };
}

/**
 * Bless a pattern for a project.
 * Validates the pattern ID and calls config.blessPattern.
 *
 * @param {string} projectRoot - Absolute path to project root
 * @param {string} patternId - Pattern ID to bless
 * @returns {Promise<{success: true, config: Object} | {success: false, error: string}>}
 */
async function blessPattern(projectRoot, patternId) {
  const validation = validatePatternId(patternId);
  if (!validation.valid) {
    return {
      success: false,
      error: validation.error,
    };
  }

  const config = await deps.blessPattern(projectRoot, patternId);
  return {
    success: true,
    config,
  };
}

/**
 * List all blessed patterns for a project.
 *
 * @param {string} projectRoot - Absolute path to project root
 * @returns {Promise<string[]>} Array of blessed pattern IDs
 */
async function listBlessedPatterns(projectRoot) {
  const config = await deps.loadConfig(projectRoot);
  return config.blessed_patterns;
}

/**
 * Check if a specific pattern is blessed for a project.
 *
 * @param {string} projectRoot - Absolute path to project root
 * @param {string} patternId - Pattern ID to check
 * @returns {Promise<boolean>} True if pattern is blessed
 */
async function isPatternBlessed(projectRoot, patternId) {
  const config = await deps.loadConfig(projectRoot);
  return config.blessed_patterns.includes(patternId);
}

module.exports = {
  validatePatternId,
  blessPattern,
  listBlessedPatterns,
  isPatternBlessed,
  // For testing
  setDeps,
  resetDeps,
};
