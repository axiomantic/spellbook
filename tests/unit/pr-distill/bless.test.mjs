import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Import the module under test
import {
  validatePatternId,
  blessPattern,
  listBlessedPatterns,
  isPatternBlessed,
  setDeps,
  resetDeps,
} from '../../../lib/pr-distill/bless.js';

describe('bless.js', () => {
  describe('validatePatternId', () => {
    describe('valid pattern IDs', () => {
      it('should accept lowercase letters only', () => {
        expect(validatePatternId('mypattern')).toEqual({ valid: true });
      });

      it('should accept letters with numbers', () => {
        expect(validatePatternId('pattern123')).toEqual({ valid: true });
      });

      it('should accept letters with hyphens', () => {
        expect(validatePatternId('my-pattern')).toEqual({ valid: true });
      });

      it('should accept complex valid patterns', () => {
        expect(validatePatternId('my-cool-pattern-v2')).toEqual({ valid: true });
      });

      it('should accept minimum length (2 chars)', () => {
        expect(validatePatternId('ab')).toEqual({ valid: true });
      });

      it('should accept maximum length (50 chars)', () => {
        const pattern = 'a'.repeat(50);
        expect(validatePatternId(pattern)).toEqual({ valid: true });
      });

      it('should accept pattern ending with number', () => {
        expect(validatePatternId('pattern1')).toEqual({ valid: true });
      });
    });

    describe('invalid pattern IDs', () => {
      it('should reject pattern shorter than 2 characters', () => {
        const result = validatePatternId('a');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('2-50');
      });

      it('should reject pattern longer than 50 characters', () => {
        const pattern = 'a'.repeat(51);
        const result = validatePatternId(pattern);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('2-50');
      });

      it('should reject uppercase letters', () => {
        const result = validatePatternId('MyPattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('lowercase');
      });

      it('should reject underscores', () => {
        const result = validatePatternId('my_pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('lowercase');
      });

      it('should reject spaces', () => {
        const result = validatePatternId('my pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('lowercase');
      });

      it('should reject special characters', () => {
        const result = validatePatternId('my@pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('lowercase');
      });

      it('should reject pattern starting with number', () => {
        const result = validatePatternId('1pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('letter');
      });

      it('should reject pattern starting with hyphen', () => {
        const result = validatePatternId('-pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('letter');
      });

      it('should reject pattern ending with hyphen', () => {
        const result = validatePatternId('pattern-');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('letter or number');
      });

      it('should reject double hyphens', () => {
        const result = validatePatternId('my--pattern');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('double hyphen');
      });

      it('should reject patterns starting with _builtin-', () => {
        const result = validatePatternId('_builtin-test');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('reserved');
      });

      it('should reject empty string', () => {
        const result = validatePatternId('');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('2-50');
      });
    });
  });

  describe('with mocked config module', () => {
    let mockConfigModule;

    beforeEach(() => {
      mockConfigModule = {
        loadConfig: vi.fn(),
        blessPattern: vi.fn(),
      };
      setDeps(mockConfigModule);
    });

    afterEach(() => {
      resetDeps();
      vi.clearAllMocks();
    });

    describe('blessPattern', () => {
      it('should validate pattern ID before blessing', async () => {
        const result = await blessPattern('/project', 'Invalid-Pattern');

        expect(result.success).toBe(false);
        expect(result.error).toContain('lowercase');
        expect(mockConfigModule.blessPattern).not.toHaveBeenCalled();
      });

      it('should reject reserved _builtin- prefix', async () => {
        const result = await blessPattern('/project', '_builtin-test');

        expect(result.success).toBe(false);
        expect(result.error).toContain('reserved');
        expect(mockConfigModule.blessPattern).not.toHaveBeenCalled();
      });

      it('should call config.blessPattern for valid pattern', async () => {
        const updatedConfig = {
          blessed_patterns: ['my-pattern'],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        };
        mockConfigModule.blessPattern.mockResolvedValue(updatedConfig);

        const result = await blessPattern('/project', 'my-pattern');

        expect(result.success).toBe(true);
        expect(result.config).toEqual(updatedConfig);
        expect(mockConfigModule.blessPattern).toHaveBeenCalledWith('/project', 'my-pattern');
      });

      it('should propagate errors from config.blessPattern', async () => {
        mockConfigModule.blessPattern.mockRejectedValue(new Error('Write failed'));

        await expect(blessPattern('/project', 'my-pattern')).rejects.toThrow('Write failed');
      });
    });

    describe('listBlessedPatterns', () => {
      it('should return empty array when no patterns blessed', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: [],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        const result = await listBlessedPatterns('/project');

        expect(result).toEqual([]);
        expect(mockConfigModule.loadConfig).toHaveBeenCalledWith('/project');
      });

      it('should return list of blessed patterns', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: ['pattern-1', 'pattern-2', 'pattern-3'],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        const result = await listBlessedPatterns('/project');

        expect(result).toEqual(['pattern-1', 'pattern-2', 'pattern-3']);
      });

      it('should propagate errors from loadConfig', async () => {
        mockConfigModule.loadConfig.mockRejectedValue(new Error('Read failed'));

        await expect(listBlessedPatterns('/project')).rejects.toThrow('Read failed');
      });
    });

    describe('isPatternBlessed', () => {
      it('should return true for blessed pattern', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: ['blessed-pattern', 'another-pattern'],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        const result = await isPatternBlessed('/project', 'blessed-pattern');

        expect(result).toBe(true);
      });

      it('should return false for non-blessed pattern', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: ['blessed-pattern'],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        const result = await isPatternBlessed('/project', 'not-blessed');

        expect(result).toBe(false);
      });

      it('should return false when blessed_patterns is empty', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: [],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        const result = await isPatternBlessed('/project', 'any-pattern');

        expect(result).toBe(false);
      });

      it('should use exact match, not substring', async () => {
        mockConfigModule.loadConfig.mockResolvedValue({
          blessed_patterns: ['pattern'],
          always_review_paths: [],
          query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
        });

        expect(await isPatternBlessed('/project', 'pattern')).toBe(true);
        expect(await isPatternBlessed('/project', 'pattern-extended')).toBe(false);
        expect(await isPatternBlessed('/project', 'my-pattern')).toBe(false);
      });
    });
  });
});
