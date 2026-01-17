import { describe, it, expect } from 'vitest';
import {
  matchPatterns,
  sortPatternsByPrecedence,
  testPattern,
} from '../../../lib/pr-distill/matcher.js';
import { BUILTIN_PATTERNS } from '../../../lib/pr-distill/patterns.js';

describe('testPattern', () => {
  const makeMockFile = (path, hunks = []) => ({
    path,
    oldPath: null,
    status: 'modified',
    hunks,
    additions: 0,
    deletions: 0,
  });

  const makeMockHunk = (lines) => ({
    oldStart: 1,
    oldCount: lines.length,
    newStart: 1,
    newCount: lines.length,
    lines,
  });

  const makeMockLine = (type, content, lineNum) => ({
    type,
    content,
    oldLineNum: type === 'add' ? null : lineNum,
    newLineNum: type === 'remove' ? null : lineNum,
  });

  describe('file matching', () => {
    it('should match file path pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'migration-file');
      const file = makeMockFile('/app/migrations/0001_initial.py');

      const result = testPattern(pattern, file);

      expect(result).not.toBeNull();
      expect(result.lines).toEqual([]);  // No line matches expected
    });

    it('should return null for non-matching file', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'migration-file');
      const file = makeMockFile('/app/views.py');

      const result = testPattern(pattern, file);

      expect(result).toBeNull();
    });
  });

  describe('line matching', () => {
    it('should match line content pattern and return line numbers', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'permission-change');
      const file = makeMockFile('/app/views.py', [
        makeMockHunk([
          makeMockLine('context', 'class MyView:', 1),
          makeMockLine('add', '    permission_classes = [IsAdmin]', 2),
          makeMockLine('context', '    def get(self):', 3),
        ]),
      ]);

      const result = testPattern(pattern, file);

      expect(result).not.toBeNull();
      expect(result.lines.length).toBe(1);
      expect(result.lines[0]).toEqual(['/app/views.py', 2]);
    });

    it('should match multiple lines', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'debug-print-removal');
      const file = makeMockFile('/app/utils.py', [
        makeMockHunk([
          makeMockLine('remove', 'print(x)', 5),
          makeMockLine('context', 'return x', 6),
          makeMockLine('remove', '  print(y)', 8),
        ]),
      ]);

      const result = testPattern(pattern, file);

      expect(result).not.toBeNull();
      expect(result.lines.length).toBe(2);
      expect(result.lines).toContainEqual(['/app/utils.py', 5]);
      expect(result.lines).toContainEqual(['/app/utils.py', 8]);
    });

    it('should not match context lines (only add/remove)', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'debug-print-removal');
      const file = makeMockFile('/app/utils.py', [
        makeMockHunk([
          makeMockLine('context', 'print(x)', 5),  // Context, should not match
          makeMockLine('add', 'logger.info(x)', 6),
        ]),
      ]);

      const result = testPattern(pattern, file);

      expect(result).toBeNull();
    });
  });

  describe('combined file + line matching', () => {
    it('should require both file and line patterns to match when both present', () => {
      // Create a pattern that has both matchFile and matchLine
      const pattern = {
        id: 'test-combined',
        confidence: 80,
        defaultCategory: 'LIKELY_SKIP',
        description: 'Test combined pattern',
        priority: 'medium',
        matchFile: /\.py$/,
        matchLine: /def test_/,
      };

      // File matches, line doesn't
      const file1 = makeMockFile('/app/test.py', [
        makeMockHunk([
          makeMockLine('add', 'def helper():', 1),
        ]),
      ]);
      expect(testPattern(pattern, file1)).toBeNull();

      // Both match
      const file2 = makeMockFile('/app/test.py', [
        makeMockHunk([
          makeMockLine('add', 'def test_something():', 1),
        ]),
      ]);
      const result = testPattern(pattern, file2);
      expect(result).not.toBeNull();
      expect(result.lines.length).toBe(1);
    });
  });
});

describe('sortPatternsByPrecedence', () => {
  it('should sort by priority tier: always_review > high > medium', () => {
    const config = { blessedPatterns: [], customPatterns: [] };
    const sorted = sortPatternsByPrecedence(config);

    // Find indices of different priority patterns
    let lastAlwaysReviewIdx = -1;
    let firstHighIdx = Infinity;
    let lastHighIdx = -1;
    let firstMediumIdx = Infinity;

    sorted.forEach((p, i) => {
      if (p.priority === 'always_review') lastAlwaysReviewIdx = i;
      if (p.priority === 'high') {
        if (i < firstHighIdx) firstHighIdx = i;
        lastHighIdx = i;
      }
      if (p.priority === 'medium' && i < firstMediumIdx) firstMediumIdx = i;
    });

    expect(lastAlwaysReviewIdx).toBeLessThan(firstHighIdx);
    expect(lastHighIdx).toBeLessThan(firstMediumIdx);
  });

  it('should place config always_review patterns before builtin always_review', () => {
    const customPattern = {
      id: 'custom-always',
      confidence: 10,
      defaultCategory: 'REVIEW_REQUIRED',
      description: 'Custom always review',
      priority: 'always_review',
      matchFile: /custom\.py$/,
    };
    const config = {
      blessedPatterns: [],
      customPatterns: [customPattern],
    };

    const sorted = sortPatternsByPrecedence(config);

    // Custom always_review should come first
    const customIdx = sorted.findIndex(p => p.id === 'custom-always');
    const builtinAlwaysIdx = sorted.findIndex(p =>
      p.id === 'migration-file' && p.priority === 'always_review'
    );

    expect(customIdx).toBeLessThan(builtinAlwaysIdx);
  });

  it('should include blessed patterns after always_review and before high', () => {
    const blessedPattern = {
      id: 'blessed-pattern',
      confidence: 90,
      defaultCategory: 'SAFE_TO_SKIP',
      description: 'Blessed by user',
      priority: 'high',  // Blessed patterns get promoted
      matchFile: /blessed\.py$/,
    };
    const config = {
      blessedPatterns: [blessedPattern],
      customPatterns: [],
    };

    const sorted = sortPatternsByPrecedence(config);
    const blessedIdx = sorted.findIndex(p => p.id === 'blessed-pattern');
    const alwaysReviewPatterns = sorted.filter(p => p.priority === 'always_review');
    const firstBuiltinHighIdx = sorted.findIndex(p =>
      p.priority === 'high' && !config.blessedPatterns.some(bp => bp.id === p.id)
    );

    // Blessed should come after all always_review
    expect(blessedIdx).toBeGreaterThan(alwaysReviewPatterns.length - 1);
    // And before or among builtin high patterns
    expect(blessedIdx).toBeLessThanOrEqual(firstBuiltinHighIdx);
  });
});

describe('matchPatterns', () => {
  const makeMockFile = (path, hunks = [], additions = 0, deletions = 0) => ({
    path,
    oldPath: null,
    status: 'modified',
    hunks,
    additions,
    deletions,
  });

  const makeMockHunk = (lines) => ({
    oldStart: 1,
    oldCount: lines.length,
    newStart: 1,
    newCount: lines.length,
    lines,
  });

  const makeMockLine = (type, content, lineNum) => ({
    type,
    content,
    oldLineNum: type === 'add' ? null : lineNum,
    newLineNum: type === 'remove' ? null : lineNum,
  });

  it('should return matched and unmatched files', () => {
    const files = [
      makeMockFile('/app/migrations/0001.py'),  // Should match migration-file
      makeMockFile('/app/random.txt'),          // Should not match
    ];
    const config = { blessedPatterns: [], customPatterns: [] };

    const result = matchPatterns(files, config);

    expect(result.matched).toBeInstanceOf(Map);
    expect(result.unmatched).toBeInstanceOf(Array);

    // Migration file should be matched
    expect(result.matched.has('migration-file')).toBe(true);
    const migrationMatch = result.matched.get('migration-file');
    expect(migrationMatch.matchedFiles).toContain('/app/migrations/0001.py');

    // Random file should be unmatched
    expect(result.unmatched.some(f => f.path === '/app/random.txt')).toBe(true);
  });

  it('should use first matching pattern (by precedence)', () => {
    // Create a file that matches both always_review and high patterns
    const files = [
      makeMockFile('/app/views.py', [
        makeMockHunk([
          makeMockLine('remove', 'print(debug)', 1),  // Would match debug-print-removal (high)
        ]),
      ]),
    ];
    const config = { blessedPatterns: [], customPatterns: [] };

    const result = matchPatterns(files, config);

    // Should match endpoint-change (always_review) first, not debug-print-removal
    expect(result.matched.has('endpoint-change')).toBe(true);
    expect(result.matched.has('debug-print-removal')).toBe(false);
  });

  it('should aggregate multiple files under same pattern', () => {
    const files = [
      makeMockFile('/app/migrations/0001.py'),
      makeMockFile('/app/migrations/0002.py'),
      makeMockFile('/other/migrations/0003.py'),
    ];
    const config = { blessedPatterns: [], customPatterns: [] };

    const result = matchPatterns(files, config);

    expect(result.matched.has('migration-file')).toBe(true);
    const match = result.matched.get('migration-file');
    expect(match.matchedFiles.length).toBe(3);
    expect(match.firstOccurrenceFile).toBe('/app/migrations/0001.py');
  });

  it('should collect matched line numbers', () => {
    const files = [
      makeMockFile('/app/utils.py', [
        makeMockHunk([
          makeMockLine('add', 'permission_classes = []', 10),
          makeMockLine('add', 'Permission.check()', 15),
        ]),
      ]),
    ];
    const config = { blessedPatterns: [], customPatterns: [] };

    const result = matchPatterns(files, config);

    // This file matches permission-change by line content
    expect(result.matched.has('permission-change')).toBe(true);
    const match = result.matched.get('permission-change');
    // Should have collected line numbers where permission-related code appears
    expect(match.matchedLines.length).toBe(2);
    expect(match.matchedLines).toContainEqual(['/app/utils.py', 10]);
    expect(match.matchedLines).toContainEqual(['/app/utils.py', 15]);
  });

  it('should handle empty file list', () => {
    const config = { blessedPatterns: [], customPatterns: [] };
    const result = matchPatterns([], config);

    expect(result.matched.size).toBe(0);
    expect(result.unmatched.length).toBe(0);
  });
});
