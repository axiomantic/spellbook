/**
 * Confidence scoring and aggregation for PR change analysis.
 * @module scorer
 */

/**
 * @typedef {'REVIEW_REQUIRED' | 'LIKELY_REVIEW' | 'UNCERTAIN' | 'LIKELY_SKIP' | 'SAFE_TO_SKIP'} ConfidenceCategory
 */

/**
 * Category thresholds for confidence scores.
 * - REVIEW_REQUIRED: 0-20
 * - LIKELY_REVIEW: 21-40
 * - UNCERTAIN: 41-60
 * - LIKELY_SKIP: 61-80
 * - SAFE_TO_SKIP: 81-100
 */
const CATEGORY_THRESHOLDS = {
  REVIEW_REQUIRED: 20,
  LIKELY_REVIEW: 40,
  UNCERTAIN: 60,
  LIKELY_SKIP: 80,
  // SAFE_TO_SKIP: 100 (implicit)
};

/**
 * Map a numeric confidence score (0-100) to a confidence category.
 *
 * @param {number} score - Confidence score (0-100)
 * @returns {ConfidenceCategory} The category for this score
 */
function categorizeConfidence(score) {
  // Clamp to valid range
  const clampedScore = Math.max(0, Math.min(100, score));

  if (clampedScore <= CATEGORY_THRESHOLDS.REVIEW_REQUIRED) {
    return 'REVIEW_REQUIRED';
  }
  if (clampedScore <= CATEGORY_THRESHOLDS.LIKELY_REVIEW) {
    return 'LIKELY_REVIEW';
  }
  if (clampedScore <= CATEGORY_THRESHOLDS.UNCERTAIN) {
    return 'UNCERTAIN';
  }
  if (clampedScore <= CATEGORY_THRESHOLDS.LIKELY_SKIP) {
    return 'LIKELY_SKIP';
  }
  return 'SAFE_TO_SKIP';
}

/**
 * Score a single file based on heuristic and AI matches.
 * Uses a weighted combination when both are present.
 *
 * @param {Object} file - FileDiff object
 * @param {Object[]} heuristicMatches - Array of PatternMatch objects from heuristics
 * @param {Object[]} aiMatches - Array of AI analysis results for this file
 * @param {Object} config - Configuration with weights
 * @param {number} [config.heuristicWeight=0.6] - Weight for heuristic score
 * @param {number} [config.aiWeight=0.4] - Weight for AI score
 * @returns {number} Combined confidence score (0-100)
 */
function scoreFile(file, heuristicMatches, aiMatches, config) {
  const heuristicWeight = config.heuristicWeight ?? 0.6;
  const aiWeight = config.aiWeight ?? 0.4;

  // Get minimum heuristic confidence (most conservative)
  const heuristicScore = heuristicMatches.length > 0
    ? Math.min(...heuristicMatches.map(m => m.confidence))
    : null;

  // Get AI confidence for this file
  const aiMatch = aiMatches.find(m => m.file === file.path);
  const aiScore = aiMatch ? aiMatch.confidence : null;

  // Combine scores based on what's available
  if (heuristicScore !== null && aiScore !== null) {
    // Both present: weighted average
    return Math.round(heuristicScore * heuristicWeight + aiScore * aiWeight);
  }

  if (heuristicScore !== null) {
    return heuristicScore;
  }

  if (aiScore !== null) {
    return aiScore;
  }

  // No matches: return uncertain (50)
  return 50;
}

/**
 * Aggregate all results into a final scored list.
 *
 * @param {Object[]} files - Array of FileDiff objects
 * @param {Map<string, Object>} heuristicResults - Map of patternId to PatternMatch
 * @param {Object[]} aiResults - Array of AI analysis results
 * @param {Object} config - Configuration object
 * @returns {Object[]} Array of ScoredChange objects, sorted by confidence ascending
 */
function aggregateResults(files, heuristicResults, aiResults, config) {
  // Build a map of file path to heuristic matches
  const fileHeuristicMatches = new Map();
  for (const [patternId, match] of heuristicResults) {
    for (const filePath of match.matchedFiles) {
      if (!fileHeuristicMatches.has(filePath)) {
        fileHeuristicMatches.set(filePath, []);
      }
      fileHeuristicMatches.get(filePath).push({
        ...match,
        patternId,
      });
    }
  }

  // Build a map of file path to AI analysis
  const fileAIAnalysis = new Map();
  for (const aiMatch of aiResults) {
    fileAIAnalysis.set(aiMatch.file, {
      confidence: aiMatch.confidence,
      explanation: aiMatch.explanation,
    });
  }

  // Score each file
  const scoredChanges = files.map(file => {
    const heuristicMatches = fileHeuristicMatches.get(file.path) || [];
    const aiAnalysis = fileAIAnalysis.get(file.path) || null;

    const confidenceScore = scoreFile(file, heuristicMatches, aiResults, config);
    const finalCategory = categorizeConfidence(confidenceScore);

    // Generate explanation
    const explanation = generateExplanation(heuristicMatches, aiAnalysis);

    return {
      fileDiff: file,
      heuristicMatches,
      aiAnalysis,
      finalCategory,
      explanation,
      confidenceScore,
    };
  });

  // Sort by confidence score ascending (needs review first)
  scoredChanges.sort((a, b) => a.confidenceScore - b.confidenceScore);

  return scoredChanges;
}

/**
 * Generate a human-readable explanation for the scoring.
 *
 * @param {Object[]} heuristicMatches - Array of heuristic matches
 * @param {Object|null} aiAnalysis - AI analysis result
 * @returns {string} Human-readable explanation
 */
function generateExplanation(heuristicMatches, aiAnalysis) {
  const parts = [];

  if (heuristicMatches.length > 0) {
    const patternIds = heuristicMatches.map(m => m.patternId).join(', ');
    parts.push(`Matched heuristic patterns: ${patternIds}`);
  }

  if (aiAnalysis && aiAnalysis.explanation) {
    parts.push(aiAnalysis.explanation);
  }

  if (parts.length === 0) {
    return 'No specific pattern matched; defaulting to uncertain';
  }

  return parts.join('. ');
}

module.exports = {
  scoreFile,
  categorizeConfidence,
  aggregateResults,
};
