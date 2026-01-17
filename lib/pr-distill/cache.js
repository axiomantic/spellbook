const fs = require('fs');
const path = require('path');
const { ErrorCode, PRDistillError } = require('./errors.js');

/**
 * Base directory for PR distillation cache.
 */
const CACHE_DIR = '/tmp/pr-distill-cache';

/**
 * Get the cache directory path for a repo and PR number.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @returns {string} Absolute path to cache directory
 */
function getCachePath(repo, prNumber) {
  // Replace slashes with dashes for filesystem safety
  const safeRepo = repo.replace(/\//g, '-');
  return path.join(CACHE_DIR, safeRepo, String(prNumber));
}

/**
 * Get cached PR data if it exists and is valid.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @param {string} headSha - Expected HEAD SHA to validate cache freshness
 * @returns {{meta: Object, diff: Object[], analysis: Object|null}|null}
 */
function getCache(repo, prNumber, headSha) {
  const cachePath = getCachePath(repo, prNumber);

  try {
    // Check if cache directory exists
    if (!fs.existsSync(cachePath)) {
      return null;
    }

    const metaPath = path.join(cachePath, 'meta.json');
    const diffPath = path.join(cachePath, 'diff.json');
    const analysisPath = path.join(cachePath, 'analysis.json');

    // Check required files exist
    if (!fs.existsSync(metaPath) || !fs.existsSync(diffPath)) {
      return null;
    }

    // Read and parse meta
    const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));

    // Validate cache freshness by checking headRefOid
    if (meta.headRefOid !== headSha) {
      return null;
    }

    // Read diff
    const diff = JSON.parse(fs.readFileSync(diffPath, 'utf8'));

    // Read analysis if it exists
    let analysis = null;
    if (fs.existsSync(analysisPath)) {
      analysis = JSON.parse(fs.readFileSync(analysisPath, 'utf8'));
    }

    return { meta, diff, analysis };
  } catch (error) {
    // Cache corrupted or unreadable
    return null;
  }
}

/**
 * Save PR data to cache.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @param {Object} meta - Metadata including headRefOid
 * @param {Object[]} diff - Parsed diff data
 * @param {Object} [analysis] - Optional analysis results
 */
function saveCache(repo, prNumber, meta, diff, analysis) {
  const cachePath = getCachePath(repo, prNumber);

  // Create directory structure
  fs.mkdirSync(cachePath, { recursive: true });

  // Write meta and diff
  fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify(meta, null, 2));
  fs.writeFileSync(path.join(cachePath, 'diff.json'), JSON.stringify(diff, null, 2));

  // Write analysis if provided
  if (analysis !== undefined && analysis !== null) {
    fs.writeFileSync(path.join(cachePath, 'analysis.json'), JSON.stringify(analysis, null, 2));
  }
}

/**
 * Delete cached data for a PR.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 */
function invalidateCache(repo, prNumber) {
  const cachePath = getCachePath(repo, prNumber);

  if (fs.existsSync(cachePath)) {
    fs.rmSync(cachePath, { recursive: true, force: true });
  }
}

/**
 * Update only the analysis portion of the cache.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @param {Object} analysis - Analysis results to save
 * @throws {PRDistillError} If cache directory doesn't exist
 */
function updateCacheAnalysis(repo, prNumber, analysis) {
  const cachePath = getCachePath(repo, prNumber);

  if (!fs.existsSync(cachePath)) {
    throw new PRDistillError(
      ErrorCode.CACHE_CORRUPTED,
      `Cache directory does not exist: ${cachePath}`,
      false,
      { repo, prNumber }
    );
  }

  fs.writeFileSync(path.join(cachePath, 'analysis.json'), JSON.stringify(analysis, null, 2));
}

module.exports = {
  CACHE_DIR,
  getCachePath,
  getCache,
  saveCache,
  invalidateCache,
  updateCacheAnalysis,
};
