/**
 * Built-in heuristic patterns for PR change analysis.
 * Patterns are matched in precedence order: always_review > high > medium
 */

/**
 * @typedef {Object} PatternDefinition
 * @property {string} id - Unique identifier
 * @property {number} confidence - 0-100, how confident we are in the categorization
 * @property {string} defaultCategory - One of: REVIEW_REQUIRED, LIKELY_REVIEW, UNCERTAIN, LIKELY_SKIP, SAFE_TO_SKIP
 * @property {string} description - Human-readable explanation
 * @property {'always_review' | 'high' | 'medium'} priority - Precedence tier
 * @property {RegExp} [matchFile] - File path pattern
 * @property {RegExp} [matchLine] - Line content pattern
 */

/**
 * ALWAYS REVIEW patterns (confidence 10-25, defaultCategory: REVIEW_REQUIRED)
 * These indicate changes that require human review regardless of other factors.
 */
const ALWAYS_REVIEW_PATTERNS = [
  {
    id: 'migration-file',
    confidence: 15,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'Database migration files require careful review for schema safety',
    priority: 'always_review',
    matchFile: /\/migrations\/.*\.py$/,
  },
  {
    id: 'permission-change',
    confidence: 20,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'Permission or authorization changes require security review',
    priority: 'always_review',
    matchLine: /Permission|permission_classes/,
  },
  {
    id: 'model-change',
    confidence: 15,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'Model changes can affect database schema and data integrity',
    priority: 'always_review',
    matchFile: /models\.py$/,
  },
  {
    id: 'signal-handler',
    confidence: 20,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'Signal handlers have implicit side effects that need careful review',
    priority: 'always_review',
    matchLine: /@receiver|Signal\(/,
  },
  {
    id: 'endpoint-change',
    confidence: 25,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'API endpoint changes can affect external consumers',
    priority: 'always_review',
    matchFile: /urls\.py$|views\.py$/,
  },
  {
    id: 'settings-change',
    confidence: 10,
    defaultCategory: 'REVIEW_REQUIRED',
    description: 'Settings changes can affect application behavior globally',
    priority: 'always_review',
    matchFile: /\/settings\//,
  },
];

/**
 * HIGH CONFIDENCE patterns (confidence 95, defaultCategory: SAFE_TO_SKIP)
 * These are low-risk changes that can usually be skipped in review.
 */
const HIGH_CONFIDENCE_PATTERNS = [
  {
    id: 'query-count-json',
    confidence: 95,
    defaultCategory: 'SAFE_TO_SKIP',
    description: 'Query count snapshots are auto-generated test artifacts',
    priority: 'high',
    matchFile: /\/query-counts\/.*-query-counts\.json$/,
  },
  {
    id: 'debug-print-removal',
    confidence: 95,
    defaultCategory: 'SAFE_TO_SKIP',
    description: 'Removing debug print statements is safe cleanup',
    priority: 'high',
    matchLine: /^\s*print\(/,
  },
  {
    id: 'import-cleanup',
    confidence: 95,
    defaultCategory: 'SAFE_TO_SKIP',
    description: 'Removing unused imports is safe cleanup',
    priority: 'high',
    matchLine: /^(import |from .+ import )/,
  },
  {
    id: 'gitignore-addition',
    confidence: 95,
    defaultCategory: 'SAFE_TO_SKIP',
    description: 'Adding entries to .gitignore is low-risk',
    priority: 'high',
    matchFile: /\.gitignore$/,
  },
  {
    id: 'backfill-command-deletion',
    confidence: 95,
    defaultCategory: 'SAFE_TO_SKIP',
    description: 'Deleting backfill management commands after completion is safe',
    priority: 'high',
    matchFile: /\/management\/commands\//,
  },
];

/**
 * MEDIUM CONFIDENCE patterns (confidence 70-85, defaultCategory: LIKELY_SKIP)
 * These are probably safe but warrant a quick glance.
 */
const MEDIUM_CONFIDENCE_PATTERNS = [
  {
    id: 'decorator-removal',
    confidence: 75,
    defaultCategory: 'LIKELY_SKIP',
    description: 'Decorator removal may indicate refactoring',
    priority: 'medium',
    matchLine: /^\s*@\w+/,
  },
  {
    id: 'factory-setup',
    confidence: 80,
    defaultCategory: 'LIKELY_SKIP',
    description: 'Factory additions are typically test setup code',
    priority: 'medium',
    matchLine: /Factory\(/,
  },
  {
    id: 'test-rename',
    confidence: 70,
    defaultCategory: 'LIKELY_SKIP',
    description: 'Test function renames usually indicate clarification',
    priority: 'medium',
    matchLine: /^\s*def test_/,
  },
  {
    id: 'test-assertion-addition',
    confidence: 85,
    defaultCategory: 'LIKELY_SKIP',
    description: 'Adding test assertions improves test coverage',
    priority: 'medium',
    matchLine: /assert_|self\.assert/,
  },
];

/**
 * All built-in patterns, sorted by priority.
 * @type {PatternDefinition[]}
 */
const BUILTIN_PATTERNS = [
  ...ALWAYS_REVIEW_PATTERNS,
  ...HIGH_CONFIDENCE_PATTERNS,
  ...MEDIUM_CONFIDENCE_PATTERNS,
];

module.exports = { BUILTIN_PATTERNS };
