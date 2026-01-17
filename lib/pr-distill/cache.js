const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const os = require('os');
const { ErrorCode, PRDistillError } = require('./errors.js');

/**
 * Base directory for PR distillation cache.
 * Uses os.tmpdir() for cross-platform compatibility.
 */
const CACHE_DIR = path.join(os.tmpdir(), 'pr-distill-cache');

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
 * @returns {Promise<{meta: Object, diff: FileDiff[], analysis: Object|null}|null>}
 */
async function getCache(repo, prNumber, headSha) {
  const cachePath = getCachePath(repo, prNumber);

  try {
    // Check if cache directory exists
    try {
      await fs.access(cachePath);
    } catch {
      return null;
    }

    const metaPath = path.join(cachePath, 'meta.json');
    const diffPath = path.join(cachePath, 'diff.json');
    const analysisPath = path.join(cachePath, 'analysis.json');

    // Check required files exist
    try {
      await Promise.all([fs.access(metaPath), fs.access(diffPath)]);
    } catch {
      return null;
    }

    // Read and parse meta
    const metaContent = await fs.readFile(metaPath, 'utf8');
    const meta = JSON.parse(metaContent);

    // Validate cache freshness by checking headRefOid
    if (meta.headRefOid !== headSha) {
      return null;
    }

    // Read diff
    const diffContent = await fs.readFile(diffPath, 'utf8');
    const diff = JSON.parse(diffContent);

    // Read analysis if it exists
    let analysis = null;
    try {
      const analysisContent = await fs.readFile(analysisPath, 'utf8');
      analysis = JSON.parse(analysisContent);
    } catch {
      // Analysis doesn't exist or is unreadable - that's ok
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
 * @param {FileDiff[]} diff - Parsed diff data
 * @param {Object} [analysis] - Optional analysis results
 * @returns {Promise<void>}
 */
async function saveCache(repo, prNumber, meta, diff, analysis) {
  const cachePath = getCachePath(repo, prNumber);

  // Create directory structure
  await fs.mkdir(cachePath, { recursive: true });

  // Write meta and diff in parallel
  const writes = [
    fs.writeFile(path.join(cachePath, 'meta.json'), JSON.stringify(meta, null, 2)),
    fs.writeFile(path.join(cachePath, 'diff.json'), JSON.stringify(diff, null, 2)),
  ];

  // Write analysis if provided
  if (analysis !== undefined && analysis !== null) {
    writes.push(fs.writeFile(path.join(cachePath, 'analysis.json'), JSON.stringify(analysis, null, 2)));
  }

  await Promise.all(writes);
}

/**
 * Delete cached data for a PR.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @returns {Promise<void>}
 */
async function invalidateCache(repo, prNumber) {
  const cachePath = getCachePath(repo, prNumber);

  try {
    await fs.rm(cachePath, { recursive: true, force: true });
  } catch {
    // Directory may not exist - that's fine
  }
}

/**
 * Update only the analysis portion of the cache.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - Pull request number
 * @param {Object} analysis - Analysis results to save
 * @returns {Promise<void>}
 * @throws {PRDistillError} If cache directory doesn't exist (CACHE_NOT_FOUND)
 */
async function updateCacheAnalysis(repo, prNumber, analysis) {
  const cachePath = getCachePath(repo, prNumber);

  try {
    await fs.access(cachePath);
  } catch {
    throw new PRDistillError(
      ErrorCode.CACHE_NOT_FOUND,
      `Cache directory does not exist: ${cachePath}`,
      false,
      { repo, prNumber }
    );
  }

  await fs.writeFile(path.join(cachePath, 'analysis.json'), JSON.stringify(analysis, null, 2));
}

module.exports = {
  CACHE_DIR,
  getCachePath,
  getCache,
  saveCache,
  invalidateCache,
  updateCacheAnalysis,
};
