import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import path from 'path';

// Import the module under test
import {
  runPhase1,
  runPhase2,
  run,
  generateAIPrompt,
  generateReport,
  setDeps,
  resetDeps,
} from '../../../lib/pr-distill/index.js';

describe('index.js orchestrator', () => {
  // Mock dependencies
  let mockDeps;

  beforeEach(() => {
    mockDeps = {
      fetchPR: vi.fn(),
      parsePRIdentifier: vi.fn(),
      parseDiff: vi.fn(),
      matchPatterns: vi.fn(),
      getCache: vi.fn(),
      saveCache: vi.fn(),
      updateCacheAnalysis: vi.fn(),
      getCachePath: vi.fn(),
      readFileSync: vi.fn(),
      existsSync: vi.fn(),
    };
    setDeps(mockDeps);
  });

  afterEach(() => {
    resetDeps();
    vi.clearAllMocks();
  });

  describe('runPhase1', () => {
    const mockPRIdentifier = { prNumber: 123, repo: 'owner/repo' };
    const mockPRData = {
      meta: {
        number: 123,
        title: 'Test PR',
        body: 'Description',
        headRefOid: 'abc123',
        baseRefName: 'main',
        additions: 10,
        deletions: 5,
        files: [{ path: 'file.py' }],
      },
      diff: 'diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py',
      repo: 'owner/repo',
    };
    const mockParsedDiff = [
      {
        path: 'file.py',
        oldPath: null,
        status: 'modified',
        hunks: [{ lines: [{ type: 'add', content: 'new line', newLineNum: 1 }] }],
        additions: 1,
        deletions: 0,
      },
    ];

    it('should fetch PR and parse diff', async () => {
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: mockParsedDiff });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const result = await runPhase1(mockPRIdentifier);

      expect(mockDeps.fetchPR).toHaveBeenCalledWith(mockPRIdentifier);
      expect(mockDeps.parseDiff).toHaveBeenCalledWith(mockPRData.diff);
      expect(result.prData).toEqual(mockPRData);
      expect(result.parsedDiff).toEqual(mockParsedDiff);
    });

    it('should run pattern matching on parsed diff', async () => {
      const mockMatched = new Map([
        ['query-count-json', {
          patternId: 'query-count-json',
          confidence: 95,
          matchedFiles: ['query-counts/test.json'],
          matchedLines: [],
          firstOccurrenceFile: 'query-counts/test.json',
        }],
      ]);
      const mockUnmatched = [{ path: 'unknown.py' }];

      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: mockMatched, unmatched: mockUnmatched });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const result = await runPhase1(mockPRIdentifier);

      expect(mockDeps.matchPatterns).toHaveBeenCalledWith(mockParsedDiff, {
        blessedPatterns: [],
        customPatterns: [],
      });
      expect(result.matchResult.matched).toBe(mockMatched);
      expect(result.matchResult.unmatched).toBe(mockUnmatched);
    });

    it('should save results to cache', async () => {
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: [] });
      mockDeps.saveCache.mockResolvedValue(undefined);

      await runPhase1(mockPRIdentifier);

      expect(mockDeps.saveCache).toHaveBeenCalledWith(
        'owner/repo',
        123,
        mockPRData.meta,
        mockParsedDiff,
        expect.objectContaining({
          matched: expect.any(Array),
          unmatched: expect.any(Array),
        })
      );
    });

    it('should return aiPrompt when unmatched files exist', async () => {
      const unmatchedFiles = [{ path: 'unknown.py', status: 'modified' }];

      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: unmatchedFiles });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const result = await runPhase1(mockPRIdentifier);

      expect(result.aiPrompt).toBeDefined();
      expect(result.aiPrompt).toContain('unknown.py');
    });

    it('should not return aiPrompt when all files matched', async () => {
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: [] });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const result = await runPhase1(mockPRIdentifier);

      expect(result.aiPrompt).toBeNull();
    });

    it('should accept custom patterns config', async () => {
      const customConfig = {
        blessedPatterns: [{ id: 'blessed-1', confidence: 90 }],
        customPatterns: [{ id: 'custom-1', confidence: 80 }],
      };

      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(mockParsedDiff);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: [] });
      mockDeps.saveCache.mockResolvedValue(undefined);

      await runPhase1(mockPRIdentifier, customConfig);

      expect(mockDeps.matchPatterns).toHaveBeenCalledWith(mockParsedDiff, customConfig);
    });
  });

  describe('runPhase2', () => {
    const mockCachePath = '/tmp/pr-distill-cache/owner-repo/123';
    const mockAnalysisPath = path.join(mockCachePath, 'analysis.json');
    const mockMetaPath = path.join(mockCachePath, 'meta.json');

    it('should load cached analysis', async () => {
      const cachedAnalysis = {
        matched: [{ patternId: 'test', matchedFiles: ['file.py'] }],
        unmatched: [{ path: 'other.py' }],
      };
      const prMeta = { number: 123, title: 'Test PR' };
      const aiResponse = { scores: [] };

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath === mockAnalysisPath) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath === mockMetaPath) {
          return JSON.stringify(prMeta);
        }
        if (filePath === 'path/to/ai-response.json') {
          return JSON.stringify(aiResponse);
        }
        throw new Error(`Unexpected file: ${filePath}`);
      });

      const result = await runPhase2('owner/repo', 123, 'path/to/ai-response.json');

      expect(mockDeps.getCachePath).toHaveBeenCalledWith('owner/repo', 123);
      expect(result.cachedAnalysis).toEqual(cachedAnalysis);
    });

    it('should read AI response file', async () => {
      const cachedAnalysis = {
        matched: [],
        unmatched: [{ path: 'file.py' }],
      };
      const prMeta = { number: 123 };
      const aiResponse = {
        scores: [{ file: 'file.py', category: 'LIKELY_SKIP', confidence: 80 }],
      };

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath === mockAnalysisPath) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath === mockMetaPath) {
          return JSON.stringify(prMeta);
        }
        if (filePath === 'path/to/ai-response.json') {
          return JSON.stringify(aiResponse);
        }
        throw new Error(`Unexpected file: ${filePath}`);
      });

      const result = await runPhase2('owner/repo', 123, 'path/to/ai-response.json');

      expect(result.aiResponse).toEqual(aiResponse);
    });

    it('should generate report with scored changes', async () => {
      const cachedAnalysis = {
        matched: [{ patternId: 'safe-pattern', matchedFiles: ['safe.py'], confidence: 95 }],
        unmatched: [{ path: 'needs-review.py' }],
      };
      const prMeta = { number: 123, title: 'Test PR' };
      const aiResponse = {
        scores: [{ file: 'needs-review.py', category: 'REVIEW_REQUIRED', confidence: 30, reason: 'Needs human review' }],
      };

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath === mockAnalysisPath) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath === mockMetaPath) {
          return JSON.stringify(prMeta);
        }
        if (filePath === 'path/to/ai-response.json') {
          return JSON.stringify(aiResponse);
        }
        throw new Error(`Unexpected file: ${filePath}`);
      });

      const result = await runPhase2('owner/repo', 123, 'path/to/ai-response.json');

      expect(result.report).toBeDefined();
      expect(typeof result.report).toBe('string');
    });

    it('should throw when cache does not exist', async () => {
      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(false);

      await expect(runPhase2('owner/repo', 123, 'path/to/ai.json'))
        .rejects.toThrow();
    });

    it('should throw when AI response file does not exist', async () => {
      const cachedAnalysis = { matched: [], unmatched: [] };
      const prMeta = { number: 123 };

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath === mockAnalysisPath) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath === mockMetaPath) {
          return JSON.stringify(prMeta);
        }
        const error = new Error('ENOENT: no such file');
        error.code = 'ENOENT';
        throw error;
      });

      await expect(runPhase2('owner/repo', 123, 'nonexistent.json'))
        .rejects.toThrow();
    });
  });

  describe('run (CLI orchestrator)', () => {
    it('should run phase 1 when --continue not provided', async () => {
      const mockPRData = {
        meta: { number: 123, headRefOid: 'abc123' },
        diff: '',
        repo: 'owner/repo',
      };

      mockDeps.parsePRIdentifier.mockReturnValue({ prNumber: 123, repo: 'owner/repo' });
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue([]);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: [] });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const output = await run({
        prIdentifier: '123',
        continue: false,
      });

      expect(mockDeps.parsePRIdentifier).toHaveBeenCalledWith('123');
      expect(mockDeps.fetchPR).toHaveBeenCalled();
      expect(output.phase).toBe(1);
    });

    it('should run phase 2 when --continue provided', async () => {
      const cachedAnalysis = { matched: [], unmatched: [] };
      const prMeta = { number: 123 };
      const aiResponse = { scores: [] };
      const mockCachePath = '/tmp/pr-distill-cache/owner-repo/123';

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath.endsWith('analysis.json')) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath.endsWith('meta.json')) {
          return JSON.stringify(prMeta);
        }
        if (filePath === 'response.json') {
          return JSON.stringify(aiResponse);
        }
        throw new Error(`Unexpected file: ${filePath}`);
      });

      const output = await run({
        prIdentifier: '123',
        continue: true,
        aiResponsePath: 'response.json',
        repo: 'owner/repo',
        prNumber: 123,
      });

      expect(output.phase).toBe(2);
    });

    it('should output AI prompt between markers in phase 1', async () => {
      const mockPRData = {
        meta: { number: 123, headRefOid: 'abc123', title: 'Test PR' },
        diff: '',
        repo: 'owner/repo',
      };
      const unmatchedFiles = [{ path: 'mystery.py', status: 'modified' }];

      mockDeps.parsePRIdentifier.mockReturnValue({ prNumber: 123, repo: 'owner/repo' });
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue(unmatchedFiles);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: unmatchedFiles });
      mockDeps.saveCache.mockResolvedValue(undefined);

      const output = await run({
        prIdentifier: '123',
        continue: false,
      });

      expect(output.stdout).toContain('__AI_PROMPT_START__');
      expect(output.stdout).toContain('__AI_PROMPT_END__');
      expect(output.stdout).toContain('mystery.py');
    });

    it('should output report between markers in phase 2', async () => {
      const cachedAnalysis = { matched: [], unmatched: [] };
      const prMeta = { number: 123 };
      const aiResponse = { scores: [] };
      const mockCachePath = '/tmp/pr-distill-cache/owner-repo/123';

      mockDeps.getCachePath.mockReturnValue(mockCachePath);
      mockDeps.existsSync.mockReturnValue(true);
      mockDeps.readFileSync.mockImplementation((filePath) => {
        if (filePath.endsWith('analysis.json')) {
          return JSON.stringify(cachedAnalysis);
        }
        if (filePath.endsWith('meta.json')) {
          return JSON.stringify(prMeta);
        }
        if (filePath === 'response.json') {
          return JSON.stringify(aiResponse);
        }
        throw new Error(`Unexpected file: ${filePath}`);
      });

      const output = await run({
        prIdentifier: '123',
        continue: true,
        aiResponsePath: 'response.json',
        repo: 'owner/repo',
        prNumber: 123,
      });

      expect(output.stdout).toContain('__REPORT_START__');
      expect(output.stdout).toContain('__REPORT_END__');
    });

    it('should handle PR URL as identifier', async () => {
      const mockPRData = {
        meta: { number: 456, headRefOid: 'def456' },
        diff: '',
        repo: 'org/project',
      };

      mockDeps.parsePRIdentifier.mockReturnValue({ prNumber: 456, repo: 'org/project' });
      mockDeps.fetchPR.mockResolvedValue(mockPRData);
      mockDeps.parseDiff.mockReturnValue([]);
      mockDeps.matchPatterns.mockReturnValue({ matched: new Map(), unmatched: [] });
      mockDeps.saveCache.mockResolvedValue(undefined);

      await run({
        prIdentifier: 'https://github.com/org/project/pull/456',
        continue: false,
      });

      expect(mockDeps.parsePRIdentifier).toHaveBeenCalledWith('https://github.com/org/project/pull/456');
    });

    it('should propagate errors from fetch phase', async () => {
      mockDeps.parsePRIdentifier.mockImplementation(() => {
        throw new Error('Invalid PR identifier');
      });

      await expect(run({
        prIdentifier: 'invalid',
        continue: false,
      })).rejects.toThrow('Invalid PR identifier');
    });
  });

  describe('generateAIPrompt', () => {
    it('should include file paths in prompt', () => {
      const prMeta = { number: 123, title: 'Test PR' };
      const unmatchedFiles = [
        { path: 'src/utils.py', status: 'modified' },
        { path: 'tests/test_utils.py', status: 'added' },
      ];

      const prompt = generateAIPrompt(prMeta, unmatchedFiles);

      expect(prompt).toContain('src/utils.py');
      expect(prompt).toContain('tests/test_utils.py');
    });

    it('should include change type in prompt', () => {
      const prMeta = { number: 123, title: 'Test PR' };
      const unmatchedFiles = [
        { path: 'new-file.py', status: 'added' },
        { path: 'deleted-file.py', status: 'deleted' },
      ];

      const prompt = generateAIPrompt(prMeta, unmatchedFiles);

      expect(prompt).toContain('added');
      expect(prompt).toContain('deleted');
    });

    it('should include PR number and title', () => {
      const prMeta = { number: 456, title: 'Fix critical bug' };
      const unmatchedFiles = [{ path: 'fix.py', status: 'modified' }];

      const prompt = generateAIPrompt(prMeta, unmatchedFiles);

      expect(prompt).toContain('#456');
      expect(prompt).toContain('Fix critical bug');
    });
  });

  describe('generateReport', () => {
    it('should include heuristic matches', () => {
      const analysis = {
        matched: [
          { patternId: 'test-pattern', matchedFiles: ['file1.py', 'file2.py'], confidence: 85 },
        ],
        unmatched: [],
        aiScores: [],
      };
      const prMeta = { number: 123 };

      const report = generateReport(analysis, prMeta);

      expect(report).toContain('test-pattern');
      expect(report).toContain('file1.py');
      expect(report).toContain('file2.py');
      expect(report).toContain('85%');
    });

    it('should include AI analysis results', () => {
      const analysis = {
        matched: [],
        unmatched: [],
        aiScores: [
          { file: 'complex.py', category: 'REVIEW_REQUIRED', confidence: 30, reason: 'Complex logic' },
        ],
      };
      const prMeta = { number: 123 };

      const report = generateReport(analysis, prMeta);

      expect(report).toContain('complex.py');
      expect(report).toContain('REVIEW_REQUIRED');
      expect(report).toContain('30%');
      expect(report).toContain('Complex logic');
    });

    it('should include summary counts', () => {
      const analysis = {
        matched: [
          { patternId: 'p1', matchedFiles: ['a.py'], confidence: 90 },
          { patternId: 'p2', matchedFiles: ['b.py'], confidence: 80 },
        ],
        unmatched: [],
        aiScores: [
          { file: 'c.py', category: 'LIKELY_SKIP', confidence: 75, reason: 'Test file' },
        ],
      };
      const prMeta = { number: 123 };

      const report = generateReport(analysis, prMeta);

      expect(report).toContain('Heuristically matched: 2');
      expect(report).toContain('AI analyzed: 1');
      expect(report).toContain('Total files: 3');
    });
  });
});
