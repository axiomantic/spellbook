import { describe, it, expect } from 'vitest';
import {
  generateAIPrompt,
  parseAIResponse,
} from '../../../lib/pr-distill/ai.js';

describe('generateAIPrompt', () => {
  const makePRMeta = (overrides = {}) => ({
    number: 123,
    title: 'Test PR',
    body: 'This is a test PR description',
    headRefOid: 'abc123',
    baseRefName: 'main',
    additions: 50,
    deletions: 20,
    files: [],
    ...overrides,
  });

  const makeUnmatchedFile = (path, hunks = []) => ({
    path,
    oldPath: null,
    status: 'modified',
    hunks,
    additions: 10,
    deletions: 5,
  });

  const makeConfig = (overrides = {}) => ({
    blessedPatterns: [],
    customPatterns: [],
    aiModel: 'gpt-4',
    ...overrides,
  });

  describe('prompt structure', () => {
    it('should generate a prompt with PR context', () => {
      const prMeta = makePRMeta({ title: 'Add new feature', body: 'Implements XYZ' });
      const unmatchedFiles = [makeUnmatchedFile('/app/new_feature.py')];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toContain('Add new feature');
      expect(prompt).toContain('Implements XYZ');
    });

    it('should include file paths in the prompt', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [
        makeUnmatchedFile('/app/service.py'),
        makeUnmatchedFile('/app/utils/helper.py'),
      ];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toContain('/app/service.py');
      expect(prompt).toContain('/app/utils/helper.py');
    });

    it('should include file status and change stats', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [
        {
          path: '/app/new.py',
          oldPath: null,
          status: 'added',
          hunks: [],
          additions: 100,
          deletions: 0,
        },
      ];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toContain('added');
      expect(prompt).toContain('100');
    });

    it('should include hunk content for context', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [
        makeUnmatchedFile('/app/service.py', [
          {
            oldStart: 1,
            oldCount: 3,
            newStart: 1,
            newCount: 4,
            lines: [
              { type: 'context', content: 'class Service:', oldLineNum: 1, newLineNum: 1 },
              { type: 'add', content: '    def new_method(self):', oldLineNum: null, newLineNum: 2 },
              { type: 'add', content: '        pass', oldLineNum: null, newLineNum: 3 },
            ],
          },
        ]),
      ];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toContain('def new_method');
    });

    it('should request JSON response format', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [makeUnmatchedFile('/app/file.py')];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toMatch(/json/i);
    });

    it('should include confidence scoring instructions', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [makeUnmatchedFile('/app/file.py')];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      // Should mention the confidence scale
      expect(prompt).toMatch(/0.*100|confidence/i);
    });
  });

  describe('edge cases', () => {
    it('should handle empty unmatched files list', () => {
      const prMeta = makePRMeta();
      const unmatchedFiles = [];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toBeDefined();
      expect(typeof prompt).toBe('string');
    });

    it('should handle PR with empty body', () => {
      const prMeta = makePRMeta({ body: '' });
      const unmatchedFiles = [makeUnmatchedFile('/app/file.py')];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toBeDefined();
    });

    it('should handle PR with null body', () => {
      const prMeta = makePRMeta({ body: null });
      const unmatchedFiles = [makeUnmatchedFile('/app/file.py')];
      const config = makeConfig();

      const prompt = generateAIPrompt(prMeta, unmatchedFiles, config);

      expect(prompt).toBeDefined();
    });
  });
});

describe('parseAIResponse', () => {
  describe('valid responses', () => {
    it('should parse a valid AI response with file assessments', () => {
      const responseJson = {
        files: [
          {
            file: '/app/service.py',
            pattern_id: 'ai-detected-refactor',
            confidence: 75,
            explanation: 'Routine refactoring with no behavioral changes',
          },
          {
            file: '/app/utils.py',
            pattern_id: 'ai-detected-logging',
            confidence: 90,
            explanation: 'Only logging additions, safe to skip',
          },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({
        file: '/app/service.py',
        patternId: 'ai-detected-refactor',
        confidence: 75,
        explanation: 'Routine refactoring with no behavioral changes',
        source: 'ai',
      });
      expect(result[1]).toEqual({
        file: '/app/utils.py',
        patternId: 'ai-detected-logging',
        confidence: 90,
        explanation: 'Only logging additions, safe to skip',
        source: 'ai',
      });
    });

    it('should handle empty files array', () => {
      const responseJson = { files: [] };

      const result = parseAIResponse(responseJson);

      expect(result).toEqual([]);
    });

    it('should normalize pattern_id to patternId', () => {
      const responseJson = {
        files: [
          {
            file: '/app/file.py',
            pattern_id: 'some-pattern',
            confidence: 50,
            explanation: 'Test',
          },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result[0].patternId).toBe('some-pattern');
      expect(result[0]).not.toHaveProperty('pattern_id');
    });
  });

  describe('edge cases', () => {
    it('should handle response with missing optional fields', () => {
      const responseJson = {
        files: [
          {
            file: '/app/file.py',
            confidence: 60,
          },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result[0].file).toBe('/app/file.py');
      expect(result[0].confidence).toBe(60);
      expect(result[0].patternId).toBe('ai-unknown');
      expect(result[0].explanation).toBe('');
      expect(result[0].source).toBe('ai');
    });

    it('should clamp confidence values to 0-100 range', () => {
      const responseJson = {
        files: [
          { file: '/app/high.py', confidence: 150, explanation: 'Too high' },
          { file: '/app/low.py', confidence: -20, explanation: 'Too low' },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result[0].confidence).toBe(100);
      expect(result[1].confidence).toBe(0);
    });

    it('should handle non-numeric confidence by defaulting to 50', () => {
      const responseJson = {
        files: [
          { file: '/app/file.py', confidence: 'high', explanation: 'Test' },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result[0].confidence).toBe(50);
    });
  });

  describe('invalid responses', () => {
    it('should throw for null response', () => {
      expect(() => parseAIResponse(null)).toThrow(/invalid.*response/i);
    });

    it('should throw for undefined response', () => {
      expect(() => parseAIResponse(undefined)).toThrow(/invalid.*response/i);
    });

    it('should throw for response without files array', () => {
      expect(() => parseAIResponse({ data: [] })).toThrow(/missing.*files/i);
    });

    it('should throw for response where files is not an array', () => {
      expect(() => parseAIResponse({ files: 'not an array' })).toThrow(/files.*array/i);
    });

    it('should skip entries without file path', () => {
      const responseJson = {
        files: [
          { file: '/app/valid.py', confidence: 80, explanation: 'Valid' },
          { confidence: 50, explanation: 'No file path' },
          { file: '', confidence: 60, explanation: 'Empty path' },
        ],
      };

      const result = parseAIResponse(responseJson);

      expect(result).toHaveLength(1);
      expect(result[0].file).toBe('/app/valid.py');
    });
  });
});
