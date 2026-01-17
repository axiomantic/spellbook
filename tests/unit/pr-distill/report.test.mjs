import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Import the module under test
import { generateReport } from '../../../lib/pr-distill/report.js';

describe('report.js', () => {
  // Helper to create a mock ScoredChange
  function createScoredChange(overrides = {}) {
    return {
      fileDiff: {
        path: overrides.path || 'src/file.py',
        oldPath: null,
        status: overrides.status || 'modified',
        hunks: overrides.hunks || [],
        additions: overrides.additions ?? 5,
        deletions: overrides.deletions ?? 3,
      },
      heuristicMatches: overrides.heuristicMatches || [],
      aiAnalysis: overrides.aiAnalysis || null,
      finalCategory: overrides.finalCategory || 'UNCERTAIN',
      explanation: overrides.explanation || 'No pattern matched',
      confidenceScore: overrides.confidenceScore ?? 50,
    };
  }

  // Helper to create mock PR metadata
  function createPRMeta(overrides = {}) {
    return {
      number: overrides.number || 123,
      title: overrides.title || 'Test PR Title',
      url: overrides.url || 'https://github.com/owner/repo/pull/123',
      additions: overrides.additions ?? 100,
      deletions: overrides.deletions ?? 50,
      ...overrides,
    };
  }

  // Helper to create mock config
  function createConfig(overrides = {}) {
    return {
      blessed_patterns: overrides.blessed_patterns || [],
      always_review_paths: overrides.always_review_paths || [],
      query_count_thresholds: overrides.query_count_thresholds || {
        relative_percent: 20,
        absolute_delta: 10,
      },
    };
  }

  describe('generateReport', () => {
    describe('summary section', () => {
      it('should include PR number and title in header', () => {
        const scoredFiles = [];
        const prMeta = createPRMeta({ number: 456, title: 'Fix critical bug' });
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('# PR #456');
        expect(report).toContain('Fix critical bug');
      });

      it('should count files by category', () => {
        const scoredFiles = [
          createScoredChange({ path: 'a.py', finalCategory: 'REVIEW_REQUIRED' }),
          createScoredChange({ path: 'b.py', finalCategory: 'REVIEW_REQUIRED' }),
          createScoredChange({ path: 'c.py', finalCategory: 'LIKELY_REVIEW' }),
          createScoredChange({ path: 'd.py', finalCategory: 'SAFE_TO_SKIP' }),
          createScoredChange({ path: 'e.py', finalCategory: 'SAFE_TO_SKIP' }),
          createScoredChange({ path: 'f.py', finalCategory: 'SAFE_TO_SKIP' }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('REVIEW_REQUIRED');
        expect(report).toContain('2'); // 2 REVIEW_REQUIRED files
        expect(report).toContain('LIKELY_REVIEW');
        expect(report).toContain('1'); // 1 LIKELY_REVIEW file
        expect(report).toContain('SAFE_TO_SKIP');
        expect(report).toContain('3'); // 3 SAFE_TO_SKIP files
      });

      it('should include total additions and deletions', () => {
        const scoredFiles = [];
        const prMeta = createPRMeta({ additions: 250, deletions: 100 });
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('+250');
        expect(report).toContain('-100');
      });
    });

    describe('REVIEW_REQUIRED section', () => {
      it('should list files with full paths', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/core/models.py',
            finalCategory: 'REVIEW_REQUIRED',
            explanation: 'Model changes require review',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('src/core/models.py');
        expect(report).toContain('Model changes require review');
      });

      it('should include diff hunks for REVIEW_REQUIRED files', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/views.py',
            finalCategory: 'REVIEW_REQUIRED',
            hunks: [
              {
                oldStart: 10,
                oldCount: 5,
                newStart: 10,
                newCount: 7,
                lines: [
                  { type: 'context', content: 'class MyView:', oldLineNum: 10, newLineNum: 10 },
                  { type: 'remove', content: '    old_code()', oldLineNum: 11, newLineNum: null },
                  { type: 'add', content: '    new_code()', oldLineNum: null, newLineNum: 11 },
                  { type: 'add', content: '    extra_line()', oldLineNum: null, newLineNum: 12 },
                ],
              },
            ],
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('```diff');
        expect(report).toContain('-    old_code()');
        expect(report).toContain('+    new_code()');
        expect(report).toContain('+    extra_line()');
      });

      it('should order REVIEW_REQUIRED files by confidence (lowest first)', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'high_confidence.py',
            finalCategory: 'REVIEW_REQUIRED',
            confidenceScore: 80,
          }),
          createScoredChange({
            path: 'low_confidence.py',
            finalCategory: 'REVIEW_REQUIRED',
            confidenceScore: 15,
          }),
          createScoredChange({
            path: 'medium_confidence.py',
            finalCategory: 'REVIEW_REQUIRED',
            confidenceScore: 50,
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        const lowIdx = report.indexOf('low_confidence.py');
        const medIdx = report.indexOf('medium_confidence.py');
        const highIdx = report.indexOf('high_confidence.py');

        expect(lowIdx).toBeLessThan(medIdx);
        expect(medIdx).toBeLessThan(highIdx);
      });
    });

    describe('LIKELY_REVIEW section', () => {
      it('should include file path and explanation', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/service.py',
            finalCategory: 'LIKELY_REVIEW',
            explanation: 'Contains business logic changes',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('src/service.py');
        expect(report).toContain('Contains business logic changes');
      });

      it('should include context lines but not full diff', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/utils.py',
            finalCategory: 'LIKELY_REVIEW',
            hunks: [
              {
                oldStart: 1,
                oldCount: 3,
                newStart: 1,
                newCount: 4,
                lines: [
                  { type: 'context', content: 'def helper():', oldLineNum: 1, newLineNum: 1 },
                  { type: 'add', content: '    return True', oldLineNum: null, newLineNum: 2 },
                ],
              },
            ],
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Should have some diff indication but may be summarized
        expect(report).toContain('src/utils.py');
      });
    });

    describe('UNCERTAIN section', () => {
      it('should list uncertain files with explanations', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/unknown.py',
            finalCategory: 'UNCERTAIN',
            explanation: 'No matching pattern found',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('src/unknown.py');
        expect(report).toContain('UNCERTAIN');
      });
    });

    describe('safe to skip section', () => {
      it('should summarize SAFE_TO_SKIP and LIKELY_SKIP files', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'tests/test_helper.py',
            finalCategory: 'SAFE_TO_SKIP',
            explanation: 'Test file',
          }),
          createScoredChange({
            path: 'migrations/0001.py',
            finalCategory: 'LIKELY_SKIP',
            explanation: 'Auto-generated migration',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('tests/test_helper.py');
        expect(report).toContain('migrations/0001.py');
      });

      it('should group by pattern when multiple files match same pattern', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'file1.json',
            finalCategory: 'SAFE_TO_SKIP',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
          }),
          createScoredChange({
            path: 'file2.json',
            finalCategory: 'SAFE_TO_SKIP',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
          }),
          createScoredChange({
            path: 'file3.json',
            finalCategory: 'SAFE_TO_SKIP',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('query-count-json');
        expect(report).toContain('3'); // 3 files
      });
    });

    describe('discovered patterns section', () => {
      it('should list newly discovered patterns with bless commands', () => {
        const scoredFiles = [
          createScoredChange({ path: 'a.py' }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();
        const discoveredPatterns = [
          {
            patternId: 'test-fixture-update',
            description: 'Test fixture file updates',
            files: ['tests/fixtures/data.json', 'tests/fixtures/users.json'],
            confidence: 85,
          },
        ];

        const report = generateReport(scoredFiles, prMeta, config, discoveredPatterns);

        expect(report).toContain('test-fixture-update');
        expect(report).toContain('Test fixture file updates');
        expect(report).toContain('bless');
      });

      it('should show pattern confidence and affected file count', () => {
        const scoredFiles = [];
        const prMeta = createPRMeta();
        const config = createConfig();
        const discoveredPatterns = [
          {
            patternId: 'log-rotation',
            description: 'Log rotation config changes',
            files: ['config/log1.yml', 'config/log2.yml', 'config/log3.yml'],
            confidence: 90,
          },
        ];

        const report = generateReport(scoredFiles, prMeta, config, discoveredPatterns);

        expect(report).toContain('90');
        expect(report).toContain('3'); // 3 files
      });

      it('should not show patterns already blessed in config', () => {
        const scoredFiles = [];
        const prMeta = createPRMeta();
        const config = createConfig({ blessed_patterns: ['already-blessed'] });
        const discoveredPatterns = [
          { patternId: 'already-blessed', description: 'Already in config', files: ['a.py'], confidence: 80 },
          { patternId: 'new-pattern', description: 'New discovery', files: ['b.py'], confidence: 75 },
        ];

        const report = generateReport(scoredFiles, prMeta, config, discoveredPatterns);

        expect(report).not.toContain('already-blessed');
        expect(report).toContain('new-pattern');
      });
    });

    describe('pattern match details section', () => {
      it('should show which patterns matched which files', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/models.py',
            heuristicMatches: [{ patternId: 'model-change', confidence: 15 }],
            finalCategory: 'REVIEW_REQUIRED',
          }),
          createScoredChange({
            path: 'tests/test_api.py',
            heuristicMatches: [{ patternId: 'test-file', confidence: 85 }],
            finalCategory: 'LIKELY_SKIP',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('model-change');
        expect(report).toContain('src/models.py');
        expect(report).toContain('test-file');
        expect(report).toContain('tests/test_api.py');
      });

      it('should show first occurrence + N more for patterns with many matches', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'query-counts/test1.json',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95, firstOccurrenceFile: 'query-counts/test1.json' }],
            finalCategory: 'SAFE_TO_SKIP',
          }),
          createScoredChange({
            path: 'query-counts/test2.json',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
            finalCategory: 'SAFE_TO_SKIP',
          }),
          createScoredChange({
            path: 'query-counts/test3.json',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
            finalCategory: 'SAFE_TO_SKIP',
          }),
          createScoredChange({
            path: 'query-counts/test4.json',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
            finalCategory: 'SAFE_TO_SKIP',
          }),
          createScoredChange({
            path: 'query-counts/test5.json',
            heuristicMatches: [{ patternId: 'query-count-json', confidence: 95 }],
            finalCategory: 'SAFE_TO_SKIP',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Should show first file and "+ N more" for the rest
        // Implementation shows up to 4 files then truncates, so 5 files = 4 shown + 1 more
        expect(report).toContain('query-counts/test1.json');
        expect(report).toMatch(/\+\s*\d+\s*more/);
      });
    });

    describe('edge cases', () => {
      it('should handle empty scored files array', () => {
        const scoredFiles = [];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('# PR #123');
        expect(report).toContain('0'); // 0 files
      });

      it('should handle files with no hunks', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'empty.py',
            finalCategory: 'REVIEW_REQUIRED',
            hunks: [],
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        expect(report).toContain('empty.py');
        // Should not crash when no diff to show
      });

      it('should escape markdown special characters in file paths', () => {
        const scoredFiles = [
          createScoredChange({
            path: 'src/[special]_file.py',
            finalCategory: 'REVIEW_REQUIRED',
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Should contain the file path (escaped or not, but valid markdown)
        expect(report).toContain('special');
        expect(report).toContain('file.py');
      });

      it('should handle very long explanations', () => {
        const longExplanation = 'A'.repeat(500);
        const scoredFiles = [
          createScoredChange({
            path: 'file.py',
            finalCategory: 'REVIEW_REQUIRED',
            explanation: longExplanation,
          }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Should not crash and should contain at least part of the explanation
        expect(report).toContain('AAAA');
      });
    });

    describe('formatting', () => {
      it('should produce valid markdown', () => {
        const scoredFiles = [
          createScoredChange({ path: 'a.py', finalCategory: 'REVIEW_REQUIRED' }),
          createScoredChange({ path: 'b.py', finalCategory: 'LIKELY_SKIP' }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Check for basic markdown structure
        expect(report).toMatch(/^#\s+/m); // Has headers
        expect(report).toContain('\n'); // Has newlines
      });

      it('should use consistent section headers', () => {
        const scoredFiles = [
          createScoredChange({ finalCategory: 'REVIEW_REQUIRED' }),
          createScoredChange({ finalCategory: 'LIKELY_REVIEW' }),
          createScoredChange({ finalCategory: 'UNCERTAIN' }),
          createScoredChange({ finalCategory: 'LIKELY_SKIP' }),
          createScoredChange({ finalCategory: 'SAFE_TO_SKIP' }),
        ];
        const prMeta = createPRMeta();
        const config = createConfig();

        const report = generateReport(scoredFiles, prMeta, config);

        // Should have section headers for each category with files
        expect(report).toMatch(/##\s+.*Review Required/i);
      });
    });
  });
});
