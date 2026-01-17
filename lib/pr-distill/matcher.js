const { BUILTIN_PATTERNS } = require('./patterns.js');

/**
 * Test a pattern against a file.
 * @param {Object} pattern - Pattern definition
 * @param {Object} file - FileDiff object
 * @returns {{lines: Array<[string, number]>}|null} Match result or null
 */
function testPattern(pattern, file) {
  const { matchFile, matchLine } = pattern;

  // Check file path pattern
  let fileMatches = true;
  if (matchFile) {
    fileMatches = matchFile.test(file.path);
  }

  if (!fileMatches) {
    return null;
  }

  // If pattern has line matcher, check lines
  if (matchLine) {
    const matchedLines = [];

    for (const hunk of file.hunks || []) {
      for (const line of hunk.lines || []) {
        // Only match add or remove lines, not context
        if (line.type === 'context') {
          continue;
        }

        if (matchLine.test(line.content)) {
          const lineNum = line.type === 'add' ? line.newLineNum : line.oldLineNum;
          matchedLines.push([file.path, lineNum]);
        }
      }
    }

    // If we have a line matcher but no lines matched, return null
    if (matchedLines.length === 0) {
      return null;
    }

    return { lines: matchedLines };
  }

  // File-only pattern matched
  return { lines: [] };
}

/**
 * Sort patterns by precedence order.
 * Order: custom always_review > blessed always_review > builtin always_review >
 *        blessed (non-always_review) > custom high > builtin high >
 *        custom medium > builtin medium
 * @param {Object} config - Configuration with blessedPatterns and customPatterns
 * @returns {Object[]} Sorted pattern array
 */
function sortPatternsByPrecedence(config) {
  const { blessedPatterns = [], customPatterns = [] } = config;

  // Separate patterns by priority tier
  const customAlwaysReview = customPatterns.filter(p => p.priority === 'always_review');
  const customHigh = customPatterns.filter(p => p.priority === 'high');
  const customMedium = customPatterns.filter(p => p.priority === 'medium');

  const builtinAlwaysReview = BUILTIN_PATTERNS.filter(p => p.priority === 'always_review');
  const builtinHigh = BUILTIN_PATTERNS.filter(p => p.priority === 'high');
  const builtinMedium = BUILTIN_PATTERNS.filter(p => p.priority === 'medium');

  // Blessed patterns are treated as high priority but come after always_review
  const sortedBlessed = blessedPatterns.filter(p => p.priority !== 'always_review');
  const blessedAlwaysReview = blessedPatterns.filter(p => p.priority === 'always_review');

  return [
    // Config always_review first
    ...customAlwaysReview,
    // Then blessed always_review
    ...blessedAlwaysReview,
    // Then builtin always_review
    ...builtinAlwaysReview,
    // Then blessed (high priority)
    ...sortedBlessed,
    // Then custom high
    ...customHigh,
    // Then builtin high
    ...builtinHigh,
    // Then custom medium
    ...customMedium,
    // Then builtin medium
    ...builtinMedium,
  ];
}

/**
 * Match patterns against a list of file diffs.
 * @param {Object[]} files - Array of FileDiff objects
 * @param {Object} config - Configuration with blessedPatterns and customPatterns
 * @returns {{matched: Map<string, Object>, unmatched: Object[]}}
 */
function matchPatterns(files, config) {
  const sortedPatterns = sortPatternsByPrecedence(config);

  /** @type {Map<string, {patternId: string, confidence: number, matchedFiles: string[], matchedLines: Array<[string, number]>, firstOccurrenceFile: string}>} */
  const matched = new Map();
  const unmatched = [];
  const matchedFilePaths = new Set();

  for (const file of files) {
    let fileMatched = false;

    for (const pattern of sortedPatterns) {
      const result = testPattern(pattern, file);

      if (result !== null) {
        fileMatched = true;
        matchedFilePaths.add(file.path);

        // Add to or create pattern match entry
        if (!matched.has(pattern.id)) {
          matched.set(pattern.id, {
            patternId: pattern.id,
            confidence: pattern.confidence,
            matchedFiles: [file.path],
            matchedLines: result.lines,
            firstOccurrenceFile: file.path,
          });
        } else {
          const existing = matched.get(pattern.id);
          existing.matchedFiles.push(file.path);
          existing.matchedLines.push(...result.lines);
        }

        // First matching pattern wins for this file
        break;
      }
    }

    if (!fileMatched) {
      unmatched.push(file);
    }
  }

  return { matched, unmatched };
}

module.exports = {
  testPattern,
  sortPatternsByPrecedence,
  matchPatterns,
};
