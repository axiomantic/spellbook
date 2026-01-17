const childProcess = require('child_process');
const { ErrorCode, PRDistillError, withRetry } = require('./errors');

/**
 * Minimum required gh CLI version.
 */
const MIN_GH_VERSION = '2.30.0';

/**
 * Regex to parse GitHub PR URLs.
 * Captures owner/repo and PR number from URLs like:
 * - https://github.com/owner/repo/pull/123
 * - https://github.com/owner/repo/pull/123/files
 */
const PR_URL_REGEX = /github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/;

/**
 * Default executor for shell commands. Can be overridden for testing.
 * @type {function(string, Object): string}
 */
let executor = (cmd, opts) => childProcess.execSync(cmd, opts);

/**
 * Set a custom executor for testing.
 * @param {function(string, Object): string} fn - Custom executor function
 */
function setExecutor(fn) {
  executor = fn;
}

/**
 * Reset executor to default.
 */
function resetExecutor() {
  executor = (cmd, opts) => childProcess.execSync(cmd, opts);
}

/**
 * Compare two semver version strings.
 * @param {string} a - First version
 * @param {string} b - Second version
 * @returns {number} -1 if a < b, 0 if a == b, 1 if a > b
 */
function compareSemver(a, b) {
  const aParts = a.split('.').map(Number);
  const bParts = b.split('.').map(Number);

  for (let i = 0; i < 3; i++) {
    const aVal = aParts[i] || 0;
    const bVal = bParts[i] || 0;
    if (aVal < bVal) return -1;
    if (aVal > bVal) return 1;
  }
  return 0;
}

/**
 * Check that gh CLI is installed and meets minimum version requirement.
 * @returns {boolean} true if version is sufficient
 * @throws {PRDistillError} GH_NOT_AUTHENTICATED if gh not installed, GH_VERSION_TOO_OLD if version is too old
 */
function checkGhVersion() {
  let output;
  try {
    output = executor('gh --version', { encoding: 'utf8' });
  } catch (error) {
    // Note: GH_NOT_AUTHENTICATED is used here for gh CLI installation check.
    // This is intentional - the same error code covers both "not installed" and
    // "not authenticated" cases since both require user action to resolve.
    throw new PRDistillError(
      ErrorCode.GH_NOT_AUTHENTICATED,
      'gh CLI is not installed or not in PATH. Please install gh: https://cli.github.com/',
      false,
      { error: error.message }
    );
  }

  // Parse version from output like "gh version 2.30.0 (2023-05-10)"
  const versionMatch = output.match(/gh version (\d+\.\d+\.\d+)/);
  if (!versionMatch) {
    throw new PRDistillError(
      ErrorCode.GH_VERSION_TOO_OLD,
      `Could not parse gh version from output: ${output}`,
      false
    );
  }

  const version = versionMatch[1];
  if (compareSemver(version, MIN_GH_VERSION) < 0) {
    throw new PRDistillError(
      ErrorCode.GH_VERSION_TOO_OLD,
      `gh CLI version ${version} is too old. Minimum required: ${MIN_GH_VERSION}. Please update: gh upgrade`,
      false,
      { version, minVersion: MIN_GH_VERSION }
    );
  }

  return true;
}

/**
 * Parse a PR identifier (number or URL) into structured format.
 * @param {string} identifier - PR number or GitHub PR URL
 * @returns {{prNumber: number, repo: string}} Parsed PR identifier
 * @throws {PRDistillError} GH_PR_NOT_FOUND if identifier is invalid or repo cannot be determined
 */
function parsePRIdentifier(identifier) {
  // Try to parse as URL first
  const urlMatch = identifier.match(PR_URL_REGEX);
  if (urlMatch) {
    return {
      prNumber: parseInt(urlMatch[2], 10),
      repo: urlMatch[1],
    };
  }

  // Try to parse as plain number
  const prNumber = parseInt(identifier, 10);
  if (!isNaN(prNumber) && prNumber > 0) {
    // Need to get repo from git remote
    let remoteUrl;
    try {
      remoteUrl = executor('git remote get-url origin', { encoding: 'utf8' }).trim();
    } catch (error) {
      throw new PRDistillError(
        ErrorCode.GH_PR_NOT_FOUND,
        'Could not determine repository from git remote. Provide a full PR URL instead.',
        false,
        { identifier }
      );
    }

    // Parse repo from HTTPS or SSH URL
    // HTTPS: https://github.com/owner/repo.git
    // SSH: git@github.com:owner/repo.git
    let repo;
    const httpsMatch = remoteUrl.match(/github\.com\/([^/]+\/[^/]+?)(?:\.git)?$/);
    const sshMatch = remoteUrl.match(/github\.com:([^/]+\/[^/]+?)(?:\.git)?$/);

    if (httpsMatch) {
      repo = httpsMatch[1];
    } else if (sshMatch) {
      repo = sshMatch[1];
    } else {
      throw new PRDistillError(
        ErrorCode.GH_PR_NOT_FOUND,
        `Could not parse GitHub repo from remote URL: ${remoteUrl}`,
        false,
        { remoteUrl }
      );
    }

    return {
      prNumber,
      repo,
    };
  }

  // Invalid identifier
  throw new PRDistillError(
    ErrorCode.GH_PR_NOT_FOUND,
    `Invalid PR identifier: ${identifier}. Provide a PR number or GitHub PR URL.`,
    false,
    { identifier }
  );
}

/**
 * Map gh CLI error to PRDistillError.
 * @param {Error} error - Original error
 * @param {Object} context - Additional context
 * @returns {PRDistillError} Mapped error
 */
function mapGhError(error, context) {
  const message = error.message || '';
  const stderr = error.stderr ? error.stderr.toString() : '';
  const combined = `${message} ${stderr}`.toLowerCase();

  if (combined.includes('could not resolve') || combined.includes('not found')) {
    return new PRDistillError(
      ErrorCode.GH_PR_NOT_FOUND,
      `PR not found: ${context.prNumber} in ${context.repo}`,
      false,
      context
    );
  }

  if (combined.includes('rate limit')) {
    return new PRDistillError(
      ErrorCode.GH_RATE_LIMITED,
      'GitHub API rate limit exceeded. Please wait and try again.',
      true,
      context
    );
  }

  if (combined.includes('not logged in') || combined.includes('gh auth login')) {
    return new PRDistillError(
      ErrorCode.GH_NOT_AUTHENTICATED,
      'Not authenticated with GitHub. Please run: gh auth login',
      false,
      context
    );
  }

  // Generic network error
  return new PRDistillError(
    ErrorCode.GH_NETWORK_ERROR,
    `GitHub API error: ${message}`,
    true,
    { ...context, originalError: message }
  );
}

/**
 * Fetch PR metadata and diff from GitHub.
 * @param {{prNumber: number, repo: string}} prIdentifier - Parsed PR identifier
 * @returns {Promise<{meta: Object, diff: string, repo: string}>} PR data
 * @throws {PRDistillError} Various error codes for different failure modes
 */
async function fetchPR(prIdentifier) {
  const { prNumber, repo } = prIdentifier;

  // Verify gh version first
  checkGhVersion();

  const context = { prNumber, repo };

  // Fetch PR metadata
  let meta;
  try {
    const metaJson = executor(
      `gh pr view ${prNumber} --repo ${repo} --json number,title,body,headRefOid,baseRefName,additions,deletions,files`,
      { encoding: 'utf8' }
    );
    meta = JSON.parse(metaJson);
  } catch (error) {
    throw mapGhError(error, context);
  }

  // Fetch PR diff
  let diff;
  try {
    diff = executor(
      `gh pr diff ${prNumber} --repo ${repo}`,
      { encoding: 'utf8' }
    );
  } catch (error) {
    throw mapGhError(error, context);
  }

  return {
    meta,
    diff,
    repo,
  };
}

// Create retry-wrapped version of fetchPR
const fetchPRWithRetry = withRetry()(fetchPR);

module.exports = {
  checkGhVersion,
  parsePRIdentifier,
  fetchPR,
  fetchPRWithRetry,
  // Export for testing
  setExecutor,
  resetExecutor,
  compareSemver,
  MIN_GH_VERSION,
  PR_URL_REGEX,
};
