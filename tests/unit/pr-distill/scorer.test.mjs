import { describe, it, expect } from 'vitest';
import {
  scoreFile,
  categorizeConfidence,
  aggregateResults,
} from '../../../lib/pr-distill/scorer.js';

describe('categorizeConfidence', () => {
  describe('category boundaries', () => {
    it('should categorize 0-20 as REVIEW_REQUIRED', () => {
      expect(categorizeConfidence(0)).toBe('REVIEW_REQUIRED');
      expect(categorizeConfidence(10)).toBe('REVIEW_REQUIRED');
      expect(categorizeConfidence(20)).toBe('REVIEW_REQUIRED');
    });

    it('should categorize 21-40 as LIKELY_REVIEW', () => {
      expect(categorizeConfidence(21)).toBe('LIKELY_REVIEW');
      expect(categorizeConfidence(30)).toBe('LIKELY_REVIEW');
      expect(categorizeConfidence(40)).toBe('LIKELY_REVIEW');
    });

    it('should categorize 41-60 as UNCERTAIN', () => {
      expect(categorizeConfidence(41)).toBe('UNCERTAIN');
      expect(categorizeConfidence(50)).toBe('UNCERTAIN');
      expect(categorizeConfidence(60)).toBe('UNCERTAIN');
    });

    it('should categorize 61-80 as LIKELY_SKIP', () => {
      expect(categorizeConfidence(61)).toBe('LIKELY_SKIP');
      expect(categorizeConfidence(70)).toBe('LIKELY_SKIP');
      expect(categorizeConfidence(80)).toBe('LIKELY_SKIP');
    });

    it('should categorize 81-100 as SAFE_TO_SKIP', () => {
      expect(categorizeConfidence(81)).toBe('SAFE_TO_SKIP');
      expect(categorizeConfidence(90)).toBe('SAFE_TO_SKIP');
      expect(categorizeConfidence(100)).toBe('SAFE_TO_SKIP');
    });
  });

  describe('edge cases', () => {
    it('should clamp values below 0 to REVIEW_REQUIRED', () => {
      expect(categorizeConfidence(-10)).toBe('REVIEW_REQUIRED');
    });

    it('should clamp values above 100 to SAFE_TO_SKIP', () => {
      expect(categorizeConfidence(150)).toBe('SAFE_TO_SKIP');
    });
  });
});

describe('scoreFile', () => {
  const makeFileDiff = (path) => ({
    path,
    oldPath: null,
    status: 'modified',
    hunks: [],
    additions: 10,
    deletions: 5,
  });

  const makeHeuristicMatch = (confidence, patternId = 'test-pattern') => ({
    patternId,
    confidence,
    matchedFiles: [],
    matchedLines: [],
    firstOccurrenceFile: '',
    source: 'heuristic',
  });

  const makeAIMatch = (filePath, confidence, explanation = 'AI explanation') => ({
    file: filePath,
    patternId: 'ai-pattern',
    confidence,
    explanation,
    source: 'ai',
  });

  const makeConfig = (overrides = {}) => ({
    heuristicWeight: 0.6,
    aiWeight: 0.4,
    ...overrides,
  });

  describe('heuristic-only scoring', () => {
    it('should use heuristic confidence when no AI match', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [makeHeuristicMatch(85)];
      const aiMatches = [];
      const config = makeConfig();

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      expect(score).toBe(85);
    });

    it('should use the lowest heuristic confidence for multiple matches', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [
        makeHeuristicMatch(90),
        makeHeuristicMatch(70),
        makeHeuristicMatch(85),
      ];
      const aiMatches = [];
      const config = makeConfig();

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      // Lowest wins (most conservative)
      expect(score).toBe(70);
    });
  });

  describe('AI-only scoring', () => {
    it('should use AI confidence when no heuristic match', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [];
      const aiMatches = [makeAIMatch('/app/file.py', 75)];
      const config = makeConfig();

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      expect(score).toBe(75);
    });
  });

  describe('combined scoring', () => {
    it('should weight heuristic and AI scores according to config', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [makeHeuristicMatch(80)];
      const aiMatches = [makeAIMatch('/app/file.py', 60)];
      const config = makeConfig({ heuristicWeight: 0.6, aiWeight: 0.4 });

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      // Expected: 80 * 0.6 + 60 * 0.4 = 48 + 24 = 72
      expect(score).toBe(72);
    });

    it('should use minimum heuristic when combining with AI', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [
        makeHeuristicMatch(90),
        makeHeuristicMatch(70),
      ];
      const aiMatches = [makeAIMatch('/app/file.py', 80)];
      const config = makeConfig({ heuristicWeight: 0.5, aiWeight: 0.5 });

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      // Expected: 70 * 0.5 + 80 * 0.5 = 35 + 40 = 75
      expect(score).toBe(75);
    });
  });

  describe('edge cases', () => {
    it('should return 50 when no matches at all (uncertain)', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [];
      const aiMatches = [];
      const config = makeConfig();

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      expect(score).toBe(50);
    });

    it('should handle zero weights gracefully', () => {
      const file = makeFileDiff('/app/file.py');
      const heuristicMatches = [makeHeuristicMatch(80)];
      const aiMatches = [makeAIMatch('/app/file.py', 60)];
      const config = makeConfig({ heuristicWeight: 1, aiWeight: 0 });

      const score = scoreFile(file, heuristicMatches, aiMatches, config);

      expect(score).toBe(80);
    });
  });
});

describe('aggregateResults', () => {
  const makeFileDiff = (path, additions = 10, deletions = 5) => ({
    path,
    oldPath: null,
    status: 'modified',
    hunks: [],
    additions,
    deletions,
  });

  const makeHeuristicMatch = (files, confidence, patternId = 'test-pattern') => ({
    patternId,
    confidence,
    matchedFiles: files,
    matchedLines: [],
    firstOccurrenceFile: files[0] || '',
  });

  const makeAIMatch = (file, confidence, explanation = 'AI explanation') => ({
    file,
    patternId: 'ai-pattern',
    confidence,
    explanation,
    source: 'ai',
  });

  const makeConfig = (overrides = {}) => ({
    heuristicWeight: 0.6,
    aiWeight: 0.4,
    ...overrides,
  });

  describe('basic aggregation', () => {
    it('should produce ScoredChange for each file', () => {
      const files = [
        makeFileDiff('/app/file1.py'),
        makeFileDiff('/app/file2.py'),
      ];
      const heuristicResults = new Map([
        ['pattern-a', makeHeuristicMatch(['/app/file1.py'], 85)],
      ]);
      const aiResults = [
        makeAIMatch('/app/file2.py', 70, 'Some AI analysis'),
      ];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result).toHaveLength(2);
      // Results are sorted by confidence ascending (needs review first)
      // file2.py has confidence 70 (AI), file1.py has confidence 85 (heuristic)
      expect(result[0].fileDiff.path).toBe('/app/file2.py');
      expect(result[1].fileDiff.path).toBe('/app/file1.py');
    });

    it('should include finalCategory based on score', () => {
      const files = [makeFileDiff('/app/file.py')];
      const heuristicResults = new Map([
        ['high-conf', makeHeuristicMatch(['/app/file.py'], 95)],
      ]);
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result[0].finalCategory).toBe('SAFE_TO_SKIP');
      expect(result[0].confidenceScore).toBe(95);
    });

    it('should include explanation from AI when available', () => {
      const files = [makeFileDiff('/app/file.py')];
      const heuristicResults = new Map();
      const aiResults = [
        makeAIMatch('/app/file.py', 80, 'This file only adds logging'),
      ];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result[0].explanation).toContain('logging');
    });

    it('should generate explanation from heuristic pattern when no AI', () => {
      const files = [makeFileDiff('/app/migrations/0001.py')];
      const heuristicResults = new Map([
        ['migration-file', {
          patternId: 'migration-file',
          confidence: 15,
          matchedFiles: ['/app/migrations/0001.py'],
          matchedLines: [],
          firstOccurrenceFile: '/app/migrations/0001.py',
        }],
      ]);
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result[0].explanation).toContain('migration-file');
    });
  });

  describe('heuristic and AI matching', () => {
    it('should associate heuristic matches with correct files', () => {
      const files = [
        makeFileDiff('/app/file1.py'),
        makeFileDiff('/app/file2.py'),
      ];
      const heuristicResults = new Map([
        ['pattern-a', makeHeuristicMatch(['/app/file1.py'], 90)],
        ['pattern-b', makeHeuristicMatch(['/app/file2.py'], 70)],
      ]);
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      // Sorted by confidence: file2 (70) before file1 (90)
      expect(result[0].heuristicMatches).toHaveLength(1);
      expect(result[0].heuristicMatches[0].patternId).toBe('pattern-b');  // file2
      expect(result[1].heuristicMatches).toHaveLength(1);
      expect(result[1].heuristicMatches[0].patternId).toBe('pattern-a');  // file1
    });

    it('should associate AI analysis with correct files', () => {
      const files = [
        makeFileDiff('/app/file1.py'),
        makeFileDiff('/app/file2.py'),
      ];
      const heuristicResults = new Map();
      const aiResults = [
        makeAIMatch('/app/file1.py', 60, 'Analysis 1'),
        makeAIMatch('/app/file2.py', 80, 'Analysis 2'),
      ];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      // Sorted by confidence: file1 (60) before file2 (80)
      expect(result[0].aiAnalysis).not.toBeNull();
      expect(result[0].aiAnalysis.confidence).toBe(60);
      expect(result[0].aiAnalysis.explanation).toBe('Analysis 1');
      expect(result[1].aiAnalysis.confidence).toBe(80);
    });
  });

  describe('edge cases', () => {
    it('should handle empty files array', () => {
      const files = [];
      const heuristicResults = new Map();
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result).toEqual([]);
    });

    it('should handle files with no matches', () => {
      const files = [makeFileDiff('/app/unknown.py')];
      const heuristicResults = new Map();
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result).toHaveLength(1);
      expect(result[0].heuristicMatches).toEqual([]);
      expect(result[0].aiAnalysis).toBeNull();
      expect(result[0].confidenceScore).toBe(50);
      expect(result[0].finalCategory).toBe('UNCERTAIN');
    });

    it('should handle file matched by multiple heuristic patterns', () => {
      const files = [makeFileDiff('/app/file.py')];
      const heuristicResults = new Map([
        ['pattern-a', makeHeuristicMatch(['/app/file.py'], 90)],
        ['pattern-b', makeHeuristicMatch(['/app/file.py'], 70)],
      ]);
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result[0].heuristicMatches).toHaveLength(2);
      // Score should use the minimum (most conservative)
      expect(result[0].confidenceScore).toBe(70);
    });
  });

  describe('sorting', () => {
    it('should sort results by confidence score ascending (needs review first)', () => {
      const files = [
        makeFileDiff('/app/safe.py'),
        makeFileDiff('/app/risky.py'),
        makeFileDiff('/app/medium.py'),
      ];
      const heuristicResults = new Map([
        ['high', makeHeuristicMatch(['/app/safe.py'], 95)],
        ['low', makeHeuristicMatch(['/app/risky.py'], 15)],
        ['med', makeHeuristicMatch(['/app/medium.py'], 50)],
      ]);
      const aiResults = [];
      const config = makeConfig();

      const result = aggregateResults(files, heuristicResults, aiResults, config);

      expect(result[0].fileDiff.path).toBe('/app/risky.py');
      expect(result[1].fileDiff.path).toBe('/app/medium.py');
      expect(result[2].fileDiff.path).toBe('/app/safe.py');
    });
  });
});
