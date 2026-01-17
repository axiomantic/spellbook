const { ErrorCode, PRDistillError } = require('./errors');

/**
 * Regex to parse the diff header line "diff --git a/path b/path"
 * Handles paths with spaces by extracting from a/ and b/ prefixes
 */
const DIFF_HEADER_REGEX = /^diff --git a\/(.+) b\/(.+)$/m;

/**
 * Regex to parse hunk headers like "@@ -1,3 +1,5 @@"
 * Captures oldStart, oldCount, newStart, newCount
 */
const HUNK_HEADER_REGEX = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

/**
 * Parse a single file's diff chunk into a FileDiff structure.
 * @param {string} chunk - Single file's diff content starting with "diff --git"
 * @returns {Object} FileDiff object
 */
function parseFileChunk(chunk) {
  const lines = chunk.split('\n');

  // Parse file paths from header
  const headerMatch = lines[0].match(DIFF_HEADER_REGEX);
  if (!headerMatch) {
    throw new PRDistillError(
      ErrorCode.DIFF_PARSE_ERROR,
      `Could not parse diff header: ${lines[0]}`,
      false,
      { chunk: chunk.substring(0, 200) }
    );
  }

  let oldPath = headerMatch[1];
  let newPath = headerMatch[2];

  // Detect file status
  let status = 'modified';
  let isBinary = false;

  for (const line of lines.slice(1, 10)) {
    if (line.startsWith('new file mode')) {
      status = 'added';
    } else if (line.startsWith('deleted file mode')) {
      status = 'deleted';
    } else if (line.startsWith('rename from ')) {
      status = 'renamed';
      oldPath = line.substring('rename from '.length);
    } else if (line.startsWith('rename to ')) {
      newPath = line.substring('rename to '.length);
    } else if (line.includes('Binary files')) {
      isBinary = true;
    }
  }

  // For renamed files, keep the oldPath, otherwise set it to null
  const finalOldPath = status === 'renamed' ? oldPath : null;

  // Binary files have no hunks to parse
  if (isBinary) {
    return {
      path: newPath,
      oldPath: finalOldPath,
      status,
      hunks: [],
      additions: 0,
      deletions: 0,
    };
  }

  // Parse hunks
  const hunks = [];
  let currentHunk = null;
  let oldLineNum = 0;
  let newLineNum = 0;
  let additions = 0;
  let deletions = 0;

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];

    // Check for hunk header
    const hunkMatch = line.match(HUNK_HEADER_REGEX);
    if (hunkMatch) {
      if (currentHunk) {
        hunks.push(currentHunk);
      }
      const hunkOldStart = parseInt(hunkMatch[1], 10);
      const hunkOldCount = hunkMatch[2] !== undefined ? parseInt(hunkMatch[2], 10) : 1;
      const hunkNewStart = parseInt(hunkMatch[3], 10);
      const hunkNewCount = hunkMatch[4] !== undefined ? parseInt(hunkMatch[4], 10) : 1;

      currentHunk = {
        oldStart: hunkOldStart,
        oldCount: hunkOldCount,
        newStart: hunkNewStart,
        newCount: hunkNewCount,
        lines: [],
      };
      oldLineNum = hunkOldStart;
      newLineNum = hunkNewStart;
      continue;
    }

    // Parse diff lines within a hunk
    if (currentHunk && line.length > 0) {
      const prefix = line[0];
      const content = line.substring(1);

      if (prefix === '+') {
        currentHunk.lines.push({
          type: 'add',
          content,
          oldLineNum: null,
          newLineNum: newLineNum,
        });
        newLineNum++;
        additions++;
      } else if (prefix === '-') {
        currentHunk.lines.push({
          type: 'remove',
          content,
          oldLineNum: oldLineNum,
          newLineNum: null,
        });
        oldLineNum++;
        deletions++;
      } else if (prefix === ' ') {
        currentHunk.lines.push({
          type: 'context',
          content,
          oldLineNum: oldLineNum,
          newLineNum: newLineNum,
        });
        oldLineNum++;
        newLineNum++;
      }
      // Ignore other prefixes like '\' for "No newline at end of file"
    }
  }

  // Don't forget the last hunk
  if (currentHunk) {
    hunks.push(currentHunk);
  }

  return {
    path: newPath,
    oldPath: finalOldPath,
    status,
    hunks,
    additions,
    deletions,
  };
}

/**
 * Parse a unified diff into an array of FileDiff objects.
 * @param {string} diff - Complete unified diff output
 * @returns {Array<Object>} Array of FileDiff objects
 */
function parseDiff(diff) {
  if (!diff || diff.trim() === '') {
    return [];
  }

  // Split by "diff --git" but keep the delimiter
  const chunks = diff.split(/(?=^diff --git )/m);

  const fileDiffs = [];

  for (const chunk of chunks) {
    if (!chunk.trim()) {
      continue;
    }

    // Each chunk should start with "diff --git"
    if (!chunk.startsWith('diff --git')) {
      continue;
    }

    try {
      const fileDiff = parseFileChunk(chunk);
      fileDiffs.push(fileDiff);
    } catch (error) {
      // If we fail to parse one file, continue with others
      // but log the error for debugging
      if (error instanceof PRDistillError) {
        console.warn(`Warning: ${error.message}`);
      } else {
        throw error;
      }
    }
  }

  return fileDiffs;
}

module.exports = {
  parseDiff,
  parseFileChunk,
};
