import { describe, it, expect } from 'vitest';
import { BUILTIN_PATTERNS } from '../../../lib/pr-distill/patterns.js';

describe('BUILTIN_PATTERNS', () => {
  it('should be an array', () => {
    expect(Array.isArray(BUILTIN_PATTERNS)).toBe(true);
  });

  it('should not be empty', () => {
    expect(BUILTIN_PATTERNS.length).toBeGreaterThan(0);
  });

  describe('pattern structure', () => {
    it('each pattern should have required fields', () => {
      for (const pattern of BUILTIN_PATTERNS) {
        expect(pattern).toHaveProperty('id');
        expect(pattern).toHaveProperty('confidence');
        expect(pattern).toHaveProperty('defaultCategory');
        expect(pattern).toHaveProperty('description');
        expect(pattern).toHaveProperty('priority');
      }
    });

    it('confidence should be a number between 0 and 100', () => {
      for (const pattern of BUILTIN_PATTERNS) {
        expect(typeof pattern.confidence).toBe('number');
        expect(pattern.confidence).toBeGreaterThanOrEqual(0);
        expect(pattern.confidence).toBeLessThanOrEqual(100);
      }
    });

    it('priority should be a valid tier', () => {
      const validPriorities = ['always_review', 'high', 'medium'];
      for (const pattern of BUILTIN_PATTERNS) {
        expect(validPriorities).toContain(pattern.priority);
      }
    });

    it('defaultCategory should be a valid category', () => {
      const validCategories = ['REVIEW_REQUIRED', 'LIKELY_REVIEW', 'UNCERTAIN', 'LIKELY_SKIP', 'SAFE_TO_SKIP'];
      for (const pattern of BUILTIN_PATTERNS) {
        expect(validCategories).toContain(pattern.defaultCategory);
      }
    });

    it('matchFile and matchLine should be RegExp or undefined', () => {
      for (const pattern of BUILTIN_PATTERNS) {
        if (pattern.matchFile !== undefined) {
          expect(pattern.matchFile).toBeInstanceOf(RegExp);
        }
        if (pattern.matchLine !== undefined) {
          expect(pattern.matchLine).toBeInstanceOf(RegExp);
        }
      }
    });
  });

  describe('ALWAYS_REVIEW patterns', () => {
    it('should include migration-file pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'migration-file');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.confidence).toBeGreaterThanOrEqual(10);
      expect(pattern.confidence).toBeLessThanOrEqual(25);
      expect(pattern.matchFile.test('/migrations/0001_initial.py')).toBe(true);
      expect(pattern.matchFile.test('/app/models.py')).toBe(false);
    });

    it('should include permission-change pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'permission-change');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.matchLine.test('Permission')).toBe(true);
      expect(pattern.matchLine.test('permission_classes')).toBe(true);
      expect(pattern.matchLine.test('some other code')).toBe(false);
    });

    it('should include model-change pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'model-change');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.matchFile.test('app/models.py')).toBe(true);
      expect(pattern.matchFile.test('app/views.py')).toBe(false);
    });

    it('should include signal-handler pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'signal-handler');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.matchLine.test('@receiver')).toBe(true);
      expect(pattern.matchLine.test('Signal(')).toBe(true);
      expect(pattern.matchLine.test('normal code')).toBe(false);
    });

    it('should include endpoint-change pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'endpoint-change');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.matchFile.test('app/urls.py')).toBe(true);
      expect(pattern.matchFile.test('app/views.py')).toBe(true);
      expect(pattern.matchFile.test('app/models.py')).toBe(false);
    });

    it('should include settings-change pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'settings-change');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('always_review');
      expect(pattern.defaultCategory).toBe('REVIEW_REQUIRED');
      expect(pattern.matchFile.test('/settings/base.py')).toBe(true);
      expect(pattern.matchFile.test('/settings/')).toBe(true);
      expect(pattern.matchFile.test('/app/views.py')).toBe(false);
    });
  });

  describe('HIGH CONFIDENCE patterns', () => {
    it('should include query-count-json pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'query-count-json');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('high');
      expect(pattern.defaultCategory).toBe('SAFE_TO_SKIP');
      expect(pattern.confidence).toBe(95);
      expect(pattern.matchFile.test('/query-counts/test-query-counts.json')).toBe(true);
      expect(pattern.matchFile.test('/app/data.json')).toBe(false);
    });

    it('should include debug-print-removal pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'debug-print-removal');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('high');
      expect(pattern.defaultCategory).toBe('SAFE_TO_SKIP');
      expect(pattern.confidence).toBe(95);
      expect(pattern.matchLine.test('  print(')).toBe(true);
      expect(pattern.matchLine.test('print(')).toBe(true);
      expect(pattern.matchLine.test('    print(x)')).toBe(true);
      expect(pattern.matchLine.test('logger.info(')).toBe(false);
    });

    it('should include import-cleanup pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'import-cleanup');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('high');
      expect(pattern.defaultCategory).toBe('SAFE_TO_SKIP');
      expect(pattern.confidence).toBe(95);
      expect(pattern.matchLine.test('import os')).toBe(true);
      expect(pattern.matchLine.test('from django import forms')).toBe(true);
      expect(pattern.matchLine.test('# import os')).toBe(false);
    });

    it('should include gitignore-addition pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'gitignore-addition');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('high');
      expect(pattern.defaultCategory).toBe('SAFE_TO_SKIP');
      expect(pattern.confidence).toBe(95);
      expect(pattern.matchFile.test('.gitignore')).toBe(true);
      expect(pattern.matchFile.test('path/to/.gitignore')).toBe(true);
      expect(pattern.matchFile.test('.gitattributes')).toBe(false);
    });

    it('should include backfill-command-deletion pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'backfill-command-deletion');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('high');
      expect(pattern.defaultCategory).toBe('SAFE_TO_SKIP');
      expect(pattern.confidence).toBe(95);
      expect(pattern.matchFile.test('/management/commands/backfill_data.py')).toBe(true);
      expect(pattern.matchFile.test('/app/views.py')).toBe(false);
    });
  });

  describe('MEDIUM CONFIDENCE patterns', () => {
    it('should include decorator-removal pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'decorator-removal');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('medium');
      expect(pattern.defaultCategory).toBe('LIKELY_SKIP');
      expect(pattern.confidence).toBeGreaterThanOrEqual(70);
      expect(pattern.confidence).toBeLessThanOrEqual(85);
      expect(pattern.matchLine.test('  @decorator')).toBe(true);
      expect(pattern.matchLine.test('@property')).toBe(true);
      expect(pattern.matchLine.test('decorator@')).toBe(false);
    });

    it('should include factory-setup pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'factory-setup');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('medium');
      expect(pattern.defaultCategory).toBe('LIKELY_SKIP');
      expect(pattern.matchLine.test('UserFactory(')).toBe(true);
      expect(pattern.matchLine.test('Factory(')).toBe(true);
      expect(pattern.matchLine.test('not a factory')).toBe(false);
    });

    it('should include test-rename pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'test-rename');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('medium');
      expect(pattern.defaultCategory).toBe('LIKELY_SKIP');
      expect(pattern.matchLine.test('  def test_something')).toBe(true);
      expect(pattern.matchLine.test('def test_')).toBe(true);
      expect(pattern.matchLine.test('def not_test')).toBe(false);
    });

    it('should include test-assertion-addition pattern', () => {
      const pattern = BUILTIN_PATTERNS.find(p => p.id === 'test-assertion-addition');
      expect(pattern).toBeDefined();
      expect(pattern.priority).toBe('medium');
      expect(pattern.defaultCategory).toBe('LIKELY_SKIP');
      expect(pattern.matchLine.test('assert_called_once')).toBe(true);
      expect(pattern.matchLine.test('self.assertEqual')).toBe(true);
      expect(pattern.matchLine.test('self.assertFalse')).toBe(true);
      expect(pattern.matchLine.test('regular code')).toBe(false);
    });
  });

  describe('pattern uniqueness', () => {
    it('all pattern ids should be unique', () => {
      const ids = BUILTIN_PATTERNS.map(p => p.id);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });
  });
});
