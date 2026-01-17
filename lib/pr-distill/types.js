/**
 * @typedef {'add' | 'remove' | 'context'} DiffLineType
 */

/**
 * A single line in a diff hunk.
 * @typedef {Object} DiffLine
 * @property {DiffLineType} type - 'add' | 'remove' | 'context'
 * @property {string} content - Line content (without +/- prefix)
 * @property {number|null} oldLineNum - Line number in old file (null for additions)
 * @property {number|null} newLineNum - Line number in new file (null for deletions)
 */

/**
 * A contiguous block of changes within a file.
 * @typedef {Object} Hunk
 * @property {number} oldStart - Starting line in old file
 * @property {number} oldCount - Number of lines in old file
 * @property {number} newStart - Starting line in new file
 * @property {number} newCount - Number of lines in new file
 * @property {DiffLine[]} lines - Array of diff lines
 */

/**
 * @typedef {'added' | 'modified' | 'deleted' | 'renamed'} FileStatus
 */

/**
 * All changes to a single file.
 * @typedef {Object} FileDiff
 * @property {string} path - File path
 * @property {string|null} oldPath - Previous path for renames
 * @property {FileStatus} status - 'added' | 'modified' | 'deleted' | 'renamed'
 * @property {Hunk[]} hunks - Array of change hunks
 * @property {number} additions - Lines added
 * @property {number} deletions - Lines deleted
 */

/**
 * Result of applying a heuristic pattern to changes.
 * @typedef {Object} PatternMatch
 * @property {string} patternId - Pattern identifier
 * @property {number} confidence - 0-100
 * @property {string[]} matchedFiles - Paths of matched files
 * @property {Array<[string, number]>} matchedLines - [file_path, line_num] tuples
 * @property {string} firstOccurrenceFile - Path for "first occurrence + N more"
 */

/**
 * Result of AI semantic analysis on unmatched changes.
 * @typedef {Object} AIAnalysis
 * @property {Array<{patternId: string, description: string, files: string[], confidence: number}>} discoveredPatterns
 * @property {Object<string, number>} confidenceAssessments - file_path -> confidence score
 * @property {Object<string, string>} explanations - file_path -> why this score
 */

/**
 * Per-file AI assessment (transformed from AIAnalysis for scoring).
 * @typedef {Object} FileAIAssessment
 * @property {number} confidence - 0-100 confidence score
 * @property {string} explanation - Why this score was assigned
 */

/**
 * @typedef {'REVIEW_REQUIRED' | 'LIKELY_REVIEW' | 'UNCERTAIN' | 'LIKELY_SKIP' | 'SAFE_TO_SKIP'} ConfidenceCategory
 */

/**
 * A file change with all analysis results and final categorization.
 * @typedef {Object} ScoredChange
 * @property {FileDiff} fileDiff
 * @property {PatternMatch[]} heuristicMatches
 * @property {FileAIAssessment|null} aiAnalysis - Per-file AI assessment
 * @property {ConfidenceCategory} finalCategory
 * @property {string} explanation - Human-readable reason for categorization
 * @property {number} confidenceScore - 0-100 numeric score
 */

/**
 * Complete analysis result for a PR.
 * @typedef {Object} DistillationResult
 * @property {number} prNumber
 * @property {string} prTitle
 * @property {string} prUrl
 * @property {number} totalFiles
 * @property {number} totalAdditions
 * @property {number} totalDeletions
 * @property {ScoredChange[]} scoredChanges
 * @property {Array<Object>} discoveredPatterns - New patterns not yet blessed
 * @property {string} generatedAt - ISO timestamp
 */

module.exports = {};  // Types only, no runtime exports
