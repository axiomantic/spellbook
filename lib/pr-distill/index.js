const fs = require('fs');
const path = require('path');
const fetchModule = require('./fetch.js');
const parseModule = require('./parse.js');
const matcherModule = require('./matcher.js');
const cacheModule = require('./cache.js');
const { BUILTIN_PATTERNS } = require('./patterns.js');
const { PRDistillError, ErrorCode } = require('./errors.js');

/**
 * Dependencies container for testing.
 * @type {{
 *   fetchPR: Function,
 *   parsePRIdentifier: Function,
 *   parseDiff: Function,
 *   matchPatterns: Function,
 *   getCache: Function,
 *   saveCache: Function,
 *   updateCacheAnalysis: Function,
 *   getCachePath: Function,
 *   readFileSync: Function,
 *   existsSync: Function
 * }}
 */
let deps = {
  fetchPR: fetchModule.fetchPR,
  parsePRIdentifier: fetchModule.parsePRIdentifier,
  parseDiff: parseModule.parseDiff,
  matchPatterns: matcherModule.matchPatterns,
  getCache: cacheModule.getCache,
  saveCache: cacheModule.saveCache,
  updateCacheAnalysis: cacheModule.updateCacheAnalysis,
  getCachePath: cacheModule.getCachePath,
  readFileSync: fs.readFileSync.bind(fs),
  existsSync: fs.existsSync.bind(fs),
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
    fetchPR: fetchModule.fetchPR,
    parsePRIdentifier: fetchModule.parsePRIdentifier,
    parseDiff: parseModule.parseDiff,
    matchPatterns: matcherModule.matchPatterns,
    getCache: cacheModule.getCache,
    saveCache: cacheModule.saveCache,
    updateCacheAnalysis: cacheModule.updateCacheAnalysis,
    getCachePath: cacheModule.getCachePath,
    readFileSync: fs.readFileSync.bind(fs),
    existsSync: fs.existsSync.bind(fs),
  };
}

/**
 * Generate an AI prompt for analyzing unmatched files.
 * @param {Object} prMeta - PR metadata
 * @param {Object[]} unmatchedFiles - Files that didn't match any pattern
 * @returns {string} Prompt for AI analysis
 */
function generateAIPrompt(prMeta, unmatchedFiles) {
  const fileList = unmatchedFiles.map(f => {
    return `- ${f.path} (${f.status})`;
  }).join('\n');

  return `Analyze the following files from PR #${prMeta.number}: "${prMeta.title}"

These files did not match any known heuristic patterns and need analysis to determine
their review priority. For each file, provide:
1. A category: REVIEW_REQUIRED, LIKELY_REVIEW, UNCERTAIN, LIKELY_SKIP, or SAFE_TO_SKIP
2. A confidence score (0-100)
3. A brief reason for your assessment

Files to analyze:
${fileList}

Respond in JSON format:
{
  "scores": [
    {
      "file": "path/to/file.py",
      "category": "LIKELY_SKIP",
      "confidence": 85,
      "reason": "Test helper file with no business logic"
    }
  ]
}`;
}

/**
 * Generate a markdown report from analysis results.
 * @param {Object} analysis - Combined heuristic and AI analysis
 * @param {Object} prMeta - PR metadata
 * @returns {string} Markdown report
 */
function generateReport(analysis, prMeta) {
  const { matched, unmatched, aiScores = [] } = analysis;

  const lines = [];
  lines.push(`# PR #${prMeta.number} Review Priority Report`);
  lines.push('');
  lines.push(`## Summary`);
  lines.push(`- Heuristically matched: ${matched.length} files`);
  lines.push(`- AI analyzed: ${aiScores.length} files`);
  lines.push(`- Total files: ${matched.length + aiScores.length}`);
  lines.push('');

  if (matched.length > 0) {
    lines.push('## Heuristic Matches');
    lines.push('');
    for (const match of matched) {
      lines.push(`### ${match.patternId} (confidence: ${match.confidence}%)`);
      lines.push('Files:');
      for (const file of match.matchedFiles) {
        lines.push(`- ${file}`);
      }
      lines.push('');
    }
  }

  if (aiScores.length > 0) {
    lines.push('## AI Analysis');
    lines.push('');
    for (const score of aiScores) {
      lines.push(`### ${score.file}`);
      lines.push(`- Category: ${score.category}`);
      lines.push(`- Confidence: ${score.confidence}%`);
      lines.push(`- Reason: ${score.reason}`);
      lines.push('');
    }
  }

  return lines.join('\n');
}

/**
 * Run Phase 1: Fetch PR, parse diff, run heuristic matching, cache results.
 * @param {{prNumber: number, repo: string}} prIdentifier - Parsed PR identifier
 * @param {Object} [config] - Pattern configuration
 * @param {Object[]} [config.blessedPatterns] - Blessed patterns
 * @param {Object[]} [config.customPatterns] - Custom patterns
 * @returns {Promise<{prData: Object, parsedDiff: Object[], matchResult: Object, aiPrompt: string|null}>}
 */
async function runPhase1(prIdentifier, config = { blessedPatterns: [], customPatterns: [] }) {
  // Fetch PR data
  const prData = await deps.fetchPR(prIdentifier);

  // Parse the diff
  const parsedDiff = deps.parseDiff(prData.diff);

  // Run pattern matching
  const matchResult = deps.matchPatterns(parsedDiff.files, config);

  // Convert Map to array for serialization
  const matchedArray = Array.from(matchResult.matched.values());

  // Prepare analysis for cache
  const analysisForCache = {
    matched: matchedArray,
    unmatched: matchResult.unmatched.map(f => ({
      path: f.path,
      status: f.status,
      additions: f.additions,
      deletions: f.deletions,
    })),
  };

  // Save to cache
  await deps.saveCache(
    prData.repo,
    prData.meta.number,
    prData.meta,
    parsedDiff,
    analysisForCache
  );

  // Generate AI prompt if there are unmatched files
  let aiPrompt = null;
  if (matchResult.unmatched.length > 0) {
    aiPrompt = generateAIPrompt(prData.meta, matchResult.unmatched);
  }

  return {
    prData,
    parsedDiff,
    matchResult,
    aiPrompt,
  };
}

/**
 * Run Phase 2: Load cache, read AI response, generate report.
 * @param {string} repo - Repository in format "owner/repo"
 * @param {number} prNumber - PR number
 * @param {string} aiResponsePath - Path to AI response JSON file
 * @returns {Promise<{cachedAnalysis: Object, aiResponse: Object, report: string}>}
 */
async function runPhase2(repo, prNumber, aiResponsePath) {
  const cachePath = deps.getCachePath(repo, prNumber);
  const analysisPath = path.join(cachePath, 'analysis.json');

  // Check cache exists
  if (!deps.existsSync(analysisPath)) {
    throw new PRDistillError(
      ErrorCode.CACHE_CORRUPTED,
      `Cache not found for ${repo}#${prNumber}. Run phase 1 first.`,
      false,
      { repo, prNumber }
    );
  }

  // Load cached analysis
  const cachedAnalysis = JSON.parse(deps.readFileSync(analysisPath, 'utf8'));

  // Load meta for report generation
  const metaPath = path.join(cachePath, 'meta.json');
  let prMeta = { number: prNumber };
  if (deps.existsSync(metaPath)) {
    prMeta = JSON.parse(deps.readFileSync(metaPath, 'utf8'));
  }

  // Read AI response
  let aiResponse = { scores: [] };
  try {
    aiResponse = JSON.parse(deps.readFileSync(aiResponsePath, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') {
      throw new PRDistillError(
        ErrorCode.CONFIG_MISSING,
        `AI response file not found: ${aiResponsePath}`,
        false,
        { aiResponsePath }
      );
    }
    throw error;
  }

  // Merge analysis with AI scores
  const mergedAnalysis = {
    ...cachedAnalysis,
    aiScores: aiResponse.scores || [],
  };

  // Generate report (placeholder for now, will be enhanced by scorer)
  const report = generateReport(mergedAnalysis, prMeta);

  return {
    cachedAnalysis,
    aiResponse,
    report,
  };
}

/**
 * Main CLI orchestrator.
 * @param {Object} options - CLI options
 * @param {string} options.prIdentifier - PR number or URL
 * @param {boolean} options.continue - Whether to run phase 2
 * @param {string} [options.aiResponsePath] - Path to AI response file (required for phase 2)
 * @param {string} [options.repo] - Repository (for phase 2)
 * @param {number} [options.prNumber] - PR number (for phase 2)
 * @returns {Promise<{phase: number, stdout: string}>}
 */
async function run(options) {
  const { prIdentifier, continue: continuePhase2, aiResponsePath, repo, prNumber } = options;

  if (continuePhase2) {
    // Phase 2
    const result = await runPhase2(repo, prNumber, aiResponsePath);

    const stdout = [
      '__REPORT_START__',
      result.report,
      '__REPORT_END__',
    ].join('\n');

    return {
      phase: 2,
      stdout,
      result,
    };
  } else {
    // Phase 1
    const parsed = deps.parsePRIdentifier(prIdentifier);
    const result = await runPhase1(parsed);

    const stdoutParts = [];

    // Output heuristic results summary
    const matchedCount = result.matchResult.matched.size;
    const unmatchedCount = result.matchResult.unmatched.length;
    stdoutParts.push(`Matched ${matchedCount} patterns, ${unmatchedCount} files unmatched`);

    // Output AI prompt if needed
    if (result.aiPrompt) {
      stdoutParts.push('');
      stdoutParts.push('__AI_PROMPT_START__');
      stdoutParts.push(result.aiPrompt);
      stdoutParts.push('__AI_PROMPT_END__');
    }

    return {
      phase: 1,
      stdout: stdoutParts.join('\n'),
      result,
    };
  }
}

module.exports = {
  runPhase1,
  runPhase2,
  run,
  generateAIPrompt,
  generateReport,
  // For testing
  setDeps,
  resetDeps,
};
