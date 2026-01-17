/**
 * Report generation for PR distillation.
 * Generates markdown reports from scored file changes.
 */

/**
 * Format a diff hunk as markdown code block.
 * @param {Object} hunk - Hunk object with lines
 * @returns {string} Formatted diff block
 */
function formatDiffHunk(hunk) {
  if (!hunk || !hunk.lines || hunk.lines.length === 0) {
    return '';
  }

  const lines = [`@@ -${hunk.oldStart},${hunk.oldCount} +${hunk.newStart},${hunk.newCount} @@`];

  for (const line of hunk.lines) {
    const prefix = line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ';
    lines.push(`${prefix}${line.content}`);
  }

  return lines.join('\n');
}

/**
 * Format full diff for a file.
 * @param {Object[]} hunks - Array of hunks
 * @returns {string} Formatted diff with code fence
 */
function formatFileDiff(hunks) {
  if (!hunks || hunks.length === 0) {
    return '';
  }

  const formatted = hunks.map(formatDiffHunk).filter(Boolean).join('\n\n');
  if (!formatted) {
    return '';
  }

  return '```diff\n' + formatted + '\n```';
}

/**
 * Escape markdown special characters in text.
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeMarkdown(text) {
  // Escape characters that could break markdown rendering
  return text.replace(/([\\`*_{}[\]()#+\-.!])/g, '\\$1');
}

/**
 * Group scored files by category.
 * @param {Object[]} scoredFiles - Array of ScoredChange objects
 * @returns {Object} Map of category to files
 */
function groupByCategory(scoredFiles) {
  const groups = {
    REVIEW_REQUIRED: [],
    LIKELY_REVIEW: [],
    UNCERTAIN: [],
    LIKELY_SKIP: [],
    SAFE_TO_SKIP: [],
  };

  for (const file of scoredFiles) {
    const category = file.finalCategory || 'UNCERTAIN';
    if (groups[category]) {
      groups[category].push(file);
    } else {
      groups.UNCERTAIN.push(file);
    }
  }

  return groups;
}

/**
 * Group files by their primary pattern match.
 * @param {Object[]} files - Array of ScoredChange objects
 * @returns {Map<string, Object[]>} Map of patternId to files
 */
function groupByPattern(files) {
  const groups = new Map();

  for (const file of files) {
    const matches = file.heuristicMatches || [];
    if (matches.length > 0) {
      const patternId = matches[0].patternId;
      if (!groups.has(patternId)) {
        groups.set(patternId, []);
      }
      groups.get(patternId).push(file);
    } else {
      // Files with no pattern match
      if (!groups.has('_unmatched')) {
        groups.set('_unmatched', []);
      }
      groups.get('_unmatched').push(file);
    }
  }

  return groups;
}

/**
 * Generate summary section of the report.
 * @param {Object[]} scoredFiles - All scored files
 * @param {Object} prMeta - PR metadata
 * @param {Object} groups - Files grouped by category
 * @returns {string[]} Array of markdown lines
 */
function generateSummary(scoredFiles, prMeta, groups) {
  const lines = [];

  lines.push(`# PR #${prMeta.number}: ${prMeta.title}`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push(`**Total files:** ${scoredFiles.length} | **Changes:** +${prMeta.additions || 0}/-${prMeta.deletions || 0}`);
  lines.push('');
  lines.push('| Category | Files |');
  lines.push('|----------|-------|');

  const categories = ['REVIEW_REQUIRED', 'LIKELY_REVIEW', 'UNCERTAIN', 'LIKELY_SKIP', 'SAFE_TO_SKIP'];
  for (const cat of categories) {
    const count = groups[cat]?.length || 0;
    if (count > 0 || cat === 'REVIEW_REQUIRED') {
      lines.push(`| ${cat} | ${count} |`);
    }
  }

  lines.push('');
  return lines;
}

/**
 * Generate the Review Required section.
 * @param {Object[]} files - Files in REVIEW_REQUIRED category
 * @returns {string[]} Array of markdown lines
 */
function generateReviewRequiredSection(files) {
  if (!files || files.length === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Review Required');
  lines.push('');
  lines.push('These files require careful review:');
  lines.push('');

  // Sort by confidence (lowest first - most uncertain = needs most attention)
  const sorted = [...files].sort((a, b) => (a.confidenceScore || 0) - (b.confidenceScore || 0));

  for (const file of sorted) {
    const filePath = file.fileDiff?.path || 'unknown';
    const explanation = file.explanation || '';
    const confidence = file.confidenceScore ?? 0;

    lines.push(`### ${filePath}`);
    lines.push('');
    lines.push(`**Confidence:** ${confidence}% | ${explanation}`);
    lines.push('');

    // Include full diff
    const diffBlock = formatFileDiff(file.fileDiff?.hunks);
    if (diffBlock) {
      lines.push(diffBlock);
      lines.push('');
    }
  }

  return lines;
}

/**
 * Generate the Likely Review section.
 * @param {Object[]} files - Files in LIKELY_REVIEW category
 * @returns {string[]} Array of markdown lines
 */
function generateLikelyReviewSection(files) {
  if (!files || files.length === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Likely Review');
  lines.push('');
  lines.push('These files probably need review:');
  lines.push('');

  for (const file of files) {
    const filePath = file.fileDiff?.path || 'unknown';
    const explanation = file.explanation || '';

    lines.push(`- **${filePath}**: ${explanation}`);
  }

  lines.push('');
  return lines;
}

/**
 * Generate the Uncertain section.
 * @param {Object[]} files - Files in UNCERTAIN category
 * @returns {string[]} Array of markdown lines
 */
function generateUncertainSection(files) {
  if (!files || files.length === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Uncertain');
  lines.push('');
  lines.push('These files could not be categorized confidently:');
  lines.push('');

  for (const file of files) {
    const filePath = file.fileDiff?.path || 'unknown';
    const explanation = file.explanation || 'No pattern matched';

    lines.push(`- **${filePath}**: ${explanation}`);
  }

  lines.push('');
  return lines;
}

/**
 * Generate the Safe to Skip section.
 * @param {Object[]} likelySkip - Files in LIKELY_SKIP category
 * @param {Object[]} safeToSkip - Files in SAFE_TO_SKIP category
 * @returns {string[]} Array of markdown lines
 */
function generateSkipSection(likelySkip, safeToSkip) {
  const allSkippable = [...(likelySkip || []), ...(safeToSkip || [])];
  if (allSkippable.length === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Safe to Skip');
  lines.push('');

  // Group by pattern for compact display
  const byPattern = groupByPattern(allSkippable);

  for (const [patternId, files] of byPattern.entries()) {
    if (patternId === '_unmatched') {
      lines.push('**Other skippable files:**');
    } else {
      lines.push(`**${patternId}** (${files.length} files):`);
    }

    // Show first few files, then "+ N more"
    const MAX_SHOW = 3;
    const toShow = files.slice(0, MAX_SHOW);
    const remaining = files.length - MAX_SHOW;

    for (const file of toShow) {
      const filePath = file.fileDiff?.path || 'unknown';
      lines.push(`- ${filePath}`);
    }

    if (remaining > 0) {
      lines.push(`- + ${remaining} more`);
    }

    lines.push('');
  }

  return lines;
}

/**
 * Generate the Discovered Patterns section.
 * @param {Object[]} discoveredPatterns - Newly discovered patterns
 * @param {Object} config - Configuration with blessed_patterns
 * @returns {string[]} Array of markdown lines
 */
function generateDiscoveredPatternsSection(discoveredPatterns, config) {
  if (!discoveredPatterns || discoveredPatterns.length === 0) {
    return [];
  }

  // Filter out already-blessed patterns
  const blessedSet = new Set(config.blessed_patterns || []);
  const newPatterns = discoveredPatterns.filter(p => !blessedSet.has(p.patternId));

  if (newPatterns.length === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Discovered Patterns');
  lines.push('');
  lines.push('The following patterns were discovered in this PR. To bless a pattern (trust it for future PRs), run the bless command:');
  lines.push('');
  lines.push('| Pattern | Description | Files | Confidence | Bless Command |');
  lines.push('|---------|-------------|-------|------------|---------------|');

  for (const pattern of newPatterns) {
    const fileCount = pattern.files?.length || 0;
    const blessCmd = `pr-distill bless ${pattern.patternId}`;
    lines.push(`| ${pattern.patternId} | ${pattern.description} | ${fileCount} | ${pattern.confidence}% | \`${blessCmd}\` |`);
  }

  lines.push('');
  return lines;
}

/**
 * Generate the Pattern Match Details section.
 * @param {Object[]} scoredFiles - All scored files
 * @returns {string[]} Array of markdown lines
 */
function generatePatternMatchDetails(scoredFiles) {
  // Collect all pattern matches
  const patternFiles = new Map();

  for (const file of scoredFiles) {
    const matches = file.heuristicMatches || [];
    for (const match of matches) {
      if (!patternFiles.has(match.patternId)) {
        patternFiles.set(match.patternId, {
          patternId: match.patternId,
          confidence: match.confidence,
          files: [],
          firstOccurrenceFile: match.firstOccurrenceFile,
        });
      }
      patternFiles.get(match.patternId).files.push(file.fileDiff?.path || 'unknown');
    }
  }

  if (patternFiles.size === 0) {
    return [];
  }

  const lines = [];
  lines.push('## Pattern Match Details');
  lines.push('');

  for (const [patternId, data] of patternFiles.entries()) {
    lines.push(`### ${patternId}`);
    lines.push(`**Confidence:** ${data.confidence}%`);
    lines.push('');

    // Show first file and "+ N more" for large matches
    const MAX_SHOW = 4;
    const firstFile = data.firstOccurrenceFile || data.files[0];
    const otherFiles = data.files.filter(f => f !== firstFile);

    lines.push(`- ${firstFile}`);

    if (otherFiles.length > 0 && otherFiles.length <= MAX_SHOW - 1) {
      for (const f of otherFiles) {
        lines.push(`- ${f}`);
      }
    } else if (otherFiles.length > MAX_SHOW - 1) {
      const toShow = otherFiles.slice(0, MAX_SHOW - 1);
      for (const f of toShow) {
        lines.push(`- ${f}`);
      }
      const remaining = otherFiles.length - (MAX_SHOW - 1);
      lines.push(`- + ${remaining} more`);
    }

    lines.push('');
  }

  return lines;
}

/**
 * Generate a full markdown report from scored files.
 * @param {Object[]} scoredFiles - Array of ScoredChange objects
 * @param {Object} prMeta - PR metadata (number, title, url, additions, deletions)
 * @param {Object} config - Configuration object
 * @param {Object[]} [discoveredPatterns] - Optional array of discovered patterns
 * @returns {string} Complete markdown report
 */
function generateReport(scoredFiles, prMeta, config, discoveredPatterns = []) {
  const groups = groupByCategory(scoredFiles);

  const sections = [
    ...generateSummary(scoredFiles, prMeta, groups),
    ...generateReviewRequiredSection(groups.REVIEW_REQUIRED),
    ...generateLikelyReviewSection(groups.LIKELY_REVIEW),
    ...generateUncertainSection(groups.UNCERTAIN),
    ...generateSkipSection(groups.LIKELY_SKIP, groups.SAFE_TO_SKIP),
    ...generateDiscoveredPatternsSection(discoveredPatterns, config),
    ...generatePatternMatchDetails(scoredFiles),
  ];

  return sections.join('\n');
}

module.exports = {
  generateReport,
  // Internal functions exported for testing
  formatDiffHunk,
  formatFileDiff,
  escapeMarkdown,
  groupByCategory,
  groupByPattern,
};
