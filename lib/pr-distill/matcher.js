const { BUILTIN_PATTERNS } = require('./patterns.js');
const { ErrorCode, PRDistillError } = require('./errors.js');

/**
 * Simple glob pattern matcher supporting * and ** wildcards.
 * @param {string} path - The file path to test
 * @param {string} pattern - The glob pattern
 * @returns {boolean} True if path matches pattern
 */
function minimatch(path, pattern) {
  if (!path || !pattern) {
    return false;
  }

  // Handle exact match first
  if (pattern === path) {
    return true;
  }

  // Handle ** only pattern
  if (pattern === '**') {
    return true;
  }

  // Convert glob pattern to regex
  // Strategy: use placeholder for ** to avoid interference with * replacement
  const DOUBLE_STAR_PLACEHOLDER = '\u0000DSTAR\u0000';

  let regexPattern = pattern
    // Escape special regex characters (except * which we handle specially)
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    // Replace ** patterns with placeholder first
    .replace(/\*\*\//g, DOUBLE_STAR_PLACEHOLDER + '/')  // **/ -> placeholder/
    .replace(/\/\*\*/g, '/' + DOUBLE_STAR_PLACEHOLDER)  // /** -> /placeholder
    .replace(/\*\*/g, DOUBLE_STAR_PLACEHOLDER)          // ** alone
    // Replace single * with non-slash matcher
    .replace(/\*/g, '[^/]*')
    // Now handle the placeholders
    // **/ at start means "match any prefix including none"
    .replace(new RegExp('^' + DOUBLE_STAR_PLACEHOLDER + '/', 'g'), '(?:.*/)?')
    // /** at end means "match any suffix including none"
    .replace(new RegExp('/' + DOUBLE_STAR_PLACEHOLDER + '$', 'g'), '(?:/.*)?')
    // /**/ in middle means "match any middle path including none"
    .replace(new RegExp('/' + DOUBLE_STAR_PLACEHOLDER + '/', 'g'), '(?:/|/.*/)')
    // Remaining ** (standalone or in other positions)
    .replace(new RegExp(DOUBLE_STAR_PLACEHOLDER, 'g'), '.*');

  // Anchor the pattern
  const regex = new RegExp(`^${regexPattern}$`);
  return regex.test(path);
}

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
 * Order: config always_review > builtin always_review > blessed > high > medium
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
  minimatch,
  testPattern,
  sortPatternsByPrecedence,
  matchPatterns,
};
