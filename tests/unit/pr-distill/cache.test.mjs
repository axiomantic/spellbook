import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import {
  CACHE_DIR,
  getCachePath,
  getCache,
  saveCache,
  invalidateCache,
  updateCacheAnalysis
} from '../../../lib/pr-distill/cache.js';

describe('cache module', () => {
  const testRepo = 'owner/test-repo';
  const testPrNumber = 123;

  // Clean up test cache dir before and after each test
  beforeEach(() => {
    const cachePath = getCachePath(testRepo, testPrNumber);
    if (fs.existsSync(cachePath)) {
      fs.rmSync(cachePath, { recursive: true, force: true });
    }
  });

  afterEach(() => {
    const cachePath = getCachePath(testRepo, testPrNumber);
    if (fs.existsSync(cachePath)) {
      fs.rmSync(cachePath, { recursive: true, force: true });
    }
  });

  describe('CACHE_DIR', () => {
    it('should be defined and end with pr-distill-cache', () => {
      expect(CACHE_DIR).toBeDefined();
      expect(CACHE_DIR.endsWith('pr-distill-cache')).toBe(true);
    });
  });

  describe('getCachePath', () => {
    it('should return path to cache directory for repo and PR', () => {
      const result = getCachePath('owner/repo', 42);
      expect(result).toBe(path.join(CACHE_DIR, 'owner-repo', '42'));
    });

    it('should handle repo names with special characters', () => {
      const result = getCachePath('my-org/my-repo', 100);
      expect(result).toBe(path.join(CACHE_DIR, 'my-org-my-repo', '100'));
    });

    it('should handle repo names with multiple slashes', () => {
      const result = getCachePath('github.com/owner/repo', 1);
      expect(result).toBe(path.join(CACHE_DIR, 'github.com-owner-repo', '1'));
    });
  });

  describe('getCache', () => {
    it('should return null when cache does not exist', async () => {
      const result = await getCache(testRepo, testPrNumber, 'abc123');
      expect(result).toBeNull();
    });

    it('should return null when meta.json is missing', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'diff.json'), '{}');

      const result = await getCache(testRepo, testPrNumber, 'abc123');
      expect(result).toBeNull();
    });

    it('should return null when headRefOid does not match', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify({
        headRefOid: 'old-sha',
        fetchedAt: new Date().toISOString(),
      }));
      fs.writeFileSync(path.join(cachePath, 'diff.json'), '[]');

      const result = await getCache(testRepo, testPrNumber, 'new-sha');
      expect(result).toBeNull();
    });

    it('should return cached data when headRefOid matches', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });

      const meta = {
        headRefOid: 'abc123',
        prNumber: testPrNumber,
        fetchedAt: new Date().toISOString(),
      };
      const diff = [{ path: 'file.py', status: 'modified' }];

      fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify(meta));
      fs.writeFileSync(path.join(cachePath, 'diff.json'), JSON.stringify(diff));

      const result = await getCache(testRepo, testPrNumber, 'abc123');

      expect(result).not.toBeNull();
      expect(result.meta).toEqual(meta);
      expect(result.diff).toEqual(diff);
      expect(result.analysis).toBeNull();  // No analysis.json
    });

    it('should include analysis when analysis.json exists', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });

      const meta = { headRefOid: 'abc123', fetchedAt: new Date().toISOString() };
      const diff = [{ path: 'file.py' }];
      const analysis = { scoredChanges: [], discoveredPatterns: [] };

      fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify(meta));
      fs.writeFileSync(path.join(cachePath, 'diff.json'), JSON.stringify(diff));
      fs.writeFileSync(path.join(cachePath, 'analysis.json'), JSON.stringify(analysis));

      const result = await getCache(testRepo, testPrNumber, 'abc123');

      expect(result.analysis).toEqual(analysis);
    });

    it('should return null when cache files are corrupted', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'meta.json'), 'not valid json');

      const result = await getCache(testRepo, testPrNumber, 'abc123');
      expect(result).toBeNull();
    });
  });

  describe('saveCache', () => {
    it('should create cache directory and write meta and diff', async () => {
      const meta = {
        headRefOid: 'abc123',
        prNumber: testPrNumber,
        fetchedAt: new Date().toISOString(),
      };
      const diff = [{ path: 'file.py', status: 'added' }];

      await saveCache(testRepo, testPrNumber, meta, diff);

      const cachePath = getCachePath(testRepo, testPrNumber);
      expect(fs.existsSync(cachePath)).toBe(true);
      expect(fs.existsSync(path.join(cachePath, 'meta.json'))).toBe(true);
      expect(fs.existsSync(path.join(cachePath, 'diff.json'))).toBe(true);

      const savedMeta = JSON.parse(fs.readFileSync(path.join(cachePath, 'meta.json'), 'utf8'));
      const savedDiff = JSON.parse(fs.readFileSync(path.join(cachePath, 'diff.json'), 'utf8'));

      expect(savedMeta).toEqual(meta);
      expect(savedDiff).toEqual(diff);
    });

    it('should write analysis when provided', async () => {
      const meta = { headRefOid: 'abc123', fetchedAt: new Date().toISOString() };
      const diff = [{ path: 'file.py' }];
      const analysis = { scoredChanges: [], discoveredPatterns: [] };

      await saveCache(testRepo, testPrNumber, meta, diff, analysis);

      const cachePath = getCachePath(testRepo, testPrNumber);
      expect(fs.existsSync(path.join(cachePath, 'analysis.json'))).toBe(true);

      const savedAnalysis = JSON.parse(fs.readFileSync(path.join(cachePath, 'analysis.json'), 'utf8'));
      expect(savedAnalysis).toEqual(analysis);
    });

    it('should not write analysis.json when analysis is not provided', async () => {
      const meta = { headRefOid: 'abc123', fetchedAt: new Date().toISOString() };
      const diff = [{ path: 'file.py' }];

      await saveCache(testRepo, testPrNumber, meta, diff);

      const cachePath = getCachePath(testRepo, testPrNumber);
      expect(fs.existsSync(path.join(cachePath, 'analysis.json'))).toBe(false);
    });

    it('should overwrite existing cache', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify({ old: true }));

      const meta = { headRefOid: 'new', fetchedAt: new Date().toISOString() };
      const diff = [{ path: 'new-file.py' }];

      await saveCache(testRepo, testPrNumber, meta, diff);

      const savedMeta = JSON.parse(fs.readFileSync(path.join(cachePath, 'meta.json'), 'utf8'));
      expect(savedMeta).toEqual(meta);
    });
  });

  describe('invalidateCache', () => {
    it('should delete cache directory', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'meta.json'), '{}');
      fs.writeFileSync(path.join(cachePath, 'diff.json'), '[]');

      await invalidateCache(testRepo, testPrNumber);

      expect(fs.existsSync(cachePath)).toBe(false);
    });

    it('should not throw when cache does not exist', async () => {
      await expect(invalidateCache(testRepo, testPrNumber)).resolves.not.toThrow();
    });
  });

  describe('updateCacheAnalysis', () => {
    it('should update only analysis.json without touching other files', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });

      const originalMeta = { headRefOid: 'abc123', fetchedAt: '2024-01-01' };
      const originalDiff = [{ path: 'file.py' }];
      fs.writeFileSync(path.join(cachePath, 'meta.json'), JSON.stringify(originalMeta));
      fs.writeFileSync(path.join(cachePath, 'diff.json'), JSON.stringify(originalDiff));

      const analysis = { scoredChanges: [{ file: 'test' }], discoveredPatterns: [] };
      await updateCacheAnalysis(testRepo, testPrNumber, analysis);

      // Analysis should be updated
      const savedAnalysis = JSON.parse(fs.readFileSync(path.join(cachePath, 'analysis.json'), 'utf8'));
      expect(savedAnalysis).toEqual(analysis);

      // Meta and diff should be unchanged
      const savedMeta = JSON.parse(fs.readFileSync(path.join(cachePath, 'meta.json'), 'utf8'));
      const savedDiff = JSON.parse(fs.readFileSync(path.join(cachePath, 'diff.json'), 'utf8'));
      expect(savedMeta).toEqual(originalMeta);
      expect(savedDiff).toEqual(originalDiff);
    });

    it('should throw when cache directory does not exist', async () => {
      await expect(
        updateCacheAnalysis(testRepo, testPrNumber, { scoredChanges: [] })
      ).rejects.toThrow();
    });

    it('should overwrite existing analysis.json', async () => {
      const cachePath = getCachePath(testRepo, testPrNumber);
      fs.mkdirSync(cachePath, { recursive: true });
      fs.writeFileSync(path.join(cachePath, 'meta.json'), '{}');
      fs.writeFileSync(path.join(cachePath, 'analysis.json'), JSON.stringify({ old: true }));

      const newAnalysis = { scoredChanges: [{ new: true }] };
      await updateCacheAnalysis(testRepo, testPrNumber, newAnalysis);

      const savedAnalysis = JSON.parse(fs.readFileSync(path.join(cachePath, 'analysis.json'), 'utf8'));
      expect(savedAnalysis).toEqual(newAnalysis);
    });
  });
});
