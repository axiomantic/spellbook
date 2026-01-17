/**
 * AI prompt generation and response parsing for PR change analysis.
 * @module ai
 */

/**
 * Generate a structured prompt for AI analysis of unmatched PR changes.
 *
 * @param {Object} prMeta - PR metadata from GitHub API
 * @param {number} prMeta.number - PR number
 * @param {string} prMeta.title - PR title
 * @param {string|null} prMeta.body - PR description
 * @param {number} prMeta.additions - Total lines added
 * @param {number} prMeta.deletions - Total lines deleted
 * @param {Object[]} unmatchedFiles - Array of FileDiff objects not matched by heuristics
 * @param {Object} config - Configuration object
 * @returns {string} Formatted prompt for AI model
 */
function generateAIPrompt(prMeta, unmatchedFiles, config) {
  const title = prMeta.title || 'Untitled PR';
  const body = prMeta.body || '';

  const filesSection = unmatchedFiles.map(file => {
    const hunksContent = formatHunks(file.hunks || []);
    return `
## File: ${file.path}
- Status: ${file.status}
- Additions: ${file.additions}, Deletions: ${file.deletions}

${hunksContent ? `### Changes:\n${hunksContent}` : '(No hunk content available)'}
`;
  }).join('\n');

  return `
You are analyzing changes from a GitHub Pull Request to determine which files can be safely skipped during code review.

# PR Context
**Title:** ${title}
**Description:** ${body || '(No description provided)'}
**Total changes:** +${prMeta.additions || 0} / -${prMeta.deletions || 0}

# Files to Analyze
The following files were not matched by heuristic patterns and need AI analysis:
${filesSection || '(No files to analyze)'}

# Task
For each file, assess the confidence level (0-100) that the file can be safely skipped during code review:
- 0-20: REVIEW_REQUIRED - Critical changes that must be reviewed
- 21-40: LIKELY_REVIEW - Probably needs review
- 41-60: UNCERTAIN - Could go either way
- 61-80: LIKELY_SKIP - Probably safe to skip
- 81-100: SAFE_TO_SKIP - Very low risk, safe to skip

Consider:
- Does the change affect business logic or behavior?
- Is it a purely mechanical change (formatting, imports, logging)?
- Does it touch security-sensitive areas (auth, permissions, data access)?
- Is it a test-only change with no production impact?

# Response Format
Respond with valid JSON in this exact format:
{
  "files": [
    {
      "file": "/path/to/file.py",
      "pattern_id": "ai-detected-pattern-name",
      "confidence": 85,
      "explanation": "Brief explanation of why this confidence level was assigned"
    }
  ]
}
`.trim();
}

/**
 * Format hunks into a readable diff representation.
 * @param {Object[]} hunks - Array of Hunk objects
 * @returns {string} Formatted hunk content
 */
function formatHunks(hunks) {
  if (!hunks || hunks.length === 0) {
    return '';
  }

  return hunks.map(hunk => {
    const lines = (hunk.lines || []).map(line => {
      const prefix = line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ';
      return `${prefix} ${line.content}`;
    }).join('\n');

    return `@@ -${hunk.oldStart},${hunk.oldCount} +${hunk.newStart},${hunk.newCount} @@\n${lines}`;
  }).join('\n\n');
}

/**
 * Parse AI response JSON into PatternMatch objects.
 *
 * @param {Object} responseJson - Parsed JSON response from AI
 * @param {Object[]} responseJson.files - Array of file assessments
 * @returns {Object[]} Array of PatternMatch-like objects with source: 'ai'
 * @throws {Error} If response is invalid or missing required fields
 */
function parseAIResponse(responseJson) {
  if (responseJson === null || responseJson === undefined) {
    throw new Error('Invalid AI response: response is null or undefined');
  }

  if (!Object.prototype.hasOwnProperty.call(responseJson, 'files')) {
    throw new Error('Invalid AI response: missing files array');
  }

  if (!Array.isArray(responseJson.files)) {
    throw new Error('Invalid AI response: files must be an array');
  }

  return responseJson.files
    .filter(entry => {
      // Skip entries without a valid file path
      return entry && typeof entry.file === 'string' && entry.file.length > 0;
    })
    .map(entry => ({
      file: entry.file,
      patternId: entry.pattern_id || 'ai-unknown',
      confidence: normalizeConfidence(entry.confidence),
      explanation: entry.explanation || '',
      source: 'ai',
    }));
}

/**
 * Normalize confidence value to 0-100 range.
 * @param {*} value - Raw confidence value
 * @returns {number} Normalized confidence (0-100)
 */
function normalizeConfidence(value) {
  if (typeof value !== 'number' || isNaN(value)) {
    return 50; // Default to uncertain
  }

  return Math.max(0, Math.min(100, value));
}

module.exports = {
  generateAIPrompt,
  parseAIResponse,
};
