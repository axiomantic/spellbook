import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import path from 'path';
import os from 'os';

// Import the module under test
import {
  CONFIG_DIR,
  getConfigPath,
  loadConfig,
  saveConfig,
  blessPattern,
  DEFAULT_CONFIG,
  setDeps,
  resetDeps,
} from '../../../lib/pr-distill/config.js';

describe('config.js', () => {
  let mockDeps;

  beforeEach(() => {
    mockDeps = {
      readFile: vi.fn(),
      writeFile: vi.fn(),
      mkdir: vi.fn(),
      access: vi.fn(),
    };
    setDeps(mockDeps);
  });

  afterEach(() => {
    resetDeps();
    vi.clearAllMocks();
  });

  describe('CONFIG_DIR', () => {
    it('should be under ~/.local/spellbook/docs/', () => {
      const homedir = os.homedir();
      expect(CONFIG_DIR).toBe(path.join(homedir, '.local', 'spellbook', 'docs'));
    });
  });

  describe('getConfigPath', () => {
    it('should encode project root path and append pr-distill-config.json', () => {
      const projectRoot = '/Users/alice/Development/myproject';
      const result = getConfigPath(projectRoot);

      // Should be: CONFIG_DIR/Users-alice-Development-myproject/pr-distill-config.json
      const expectedEncoded = 'Users-alice-Development-myproject';
      expect(result).toBe(path.join(CONFIG_DIR, expectedEncoded, 'pr-distill-config.json'));
    });

    it('should handle Windows-style paths', () => {
      // On non-Windows, this tests that forward slashes are handled
      const projectRoot = '/home/user/project';
      const result = getConfigPath(projectRoot);

      const expectedEncoded = 'home-user-project';
      expect(result).toBe(path.join(CONFIG_DIR, expectedEncoded, 'pr-distill-config.json'));
    });

    it('should handle paths with multiple slashes', () => {
      const projectRoot = '/Users/bob/Code/github/spellbook';
      const result = getConfigPath(projectRoot);

      const expectedEncoded = 'Users-bob-Code-github-spellbook';
      expect(result).toBe(path.join(CONFIG_DIR, expectedEncoded, 'pr-distill-config.json'));
    });
  });

  describe('DEFAULT_CONFIG', () => {
    it('should have blessed_patterns as empty array', () => {
      expect(DEFAULT_CONFIG.blessed_patterns).toEqual([]);
    });

    it('should have always_review_paths as empty array', () => {
      expect(DEFAULT_CONFIG.always_review_paths).toEqual([]);
    });

    it('should have query_count_thresholds with correct defaults', () => {
      expect(DEFAULT_CONFIG.query_count_thresholds).toEqual({
        relative_percent: 20,
        absolute_delta: 10,
      });
    });
  });

  describe('loadConfig', () => {
    it('should return default config when file does not exist', async () => {
      mockDeps.access.mockRejectedValue(new Error('ENOENT'));

      const result = await loadConfig('/project/root');

      expect(result).toEqual(DEFAULT_CONFIG);
    });

    it('should load and parse existing config file', async () => {
      const existingConfig = {
        blessed_patterns: ['pattern-1', 'pattern-2'],
        always_review_paths: ['src/critical/'],
        query_count_thresholds: { relative_percent: 30, absolute_delta: 15 },
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(existingConfig));

      const result = await loadConfig('/project/root');

      expect(result).toEqual(existingConfig);
    });

    it('should merge with defaults for missing keys', async () => {
      const partialConfig = {
        blessed_patterns: ['pattern-1'],
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(partialConfig));

      const result = await loadConfig('/project/root');

      expect(result.blessed_patterns).toEqual(['pattern-1']);
      expect(result.always_review_paths).toEqual([]); // From default
      expect(result.query_count_thresholds).toEqual({
        relative_percent: 20,
        absolute_delta: 10,
      }); // From default
    });

    it('should pass correct path to readFile', async () => {
      const projectRoot = '/Users/test/myproject';
      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify({}));

      await loadConfig(projectRoot);

      const expectedPath = getConfigPath(projectRoot);
      expect(mockDeps.readFile).toHaveBeenCalledWith(expectedPath, 'utf8');
    });
  });

  describe('saveConfig', () => {
    it('should create directory and write config file', async () => {
      const config = {
        blessed_patterns: ['test-pattern'],
        always_review_paths: [],
        query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
      };

      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      await saveConfig('/project/root', config);

      expect(mockDeps.mkdir).toHaveBeenCalledWith(
        expect.stringContaining('project-root'),
        { recursive: true }
      );
      expect(mockDeps.writeFile).toHaveBeenCalledWith(
        expect.stringContaining('pr-distill-config.json'),
        JSON.stringify(config, null, 2)
      );
    });

    it('should pretty-print JSON with 2-space indentation', async () => {
      const config = { blessed_patterns: ['a', 'b'] };

      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      await saveConfig('/project', config);

      const writtenContent = mockDeps.writeFile.mock.calls[0][1];
      expect(writtenContent).toContain('\n');
      expect(writtenContent).toContain('  ');
    });
  });

  describe('blessPattern', () => {
    it('should add pattern to empty blessed_patterns array', async () => {
      const existingConfig = {
        blessed_patterns: [],
        always_review_paths: [],
        query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(existingConfig));
      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      const result = await blessPattern('/project', 'new-pattern');

      expect(result.blessed_patterns).toContain('new-pattern');
      expect(mockDeps.writeFile).toHaveBeenCalled();
    });

    it('should not duplicate existing blessed pattern', async () => {
      const existingConfig = {
        blessed_patterns: ['existing-pattern'],
        always_review_paths: [],
        query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(existingConfig));
      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      const result = await blessPattern('/project', 'existing-pattern');

      expect(result.blessed_patterns).toEqual(['existing-pattern']);
      expect(result.blessed_patterns.filter(p => p === 'existing-pattern').length).toBe(1);
    });

    it('should append to existing blessed patterns', async () => {
      const existingConfig = {
        blessed_patterns: ['pattern-1', 'pattern-2'],
        always_review_paths: [],
        query_count_thresholds: { relative_percent: 20, absolute_delta: 10 },
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(existingConfig));
      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      const result = await blessPattern('/project', 'pattern-3');

      expect(result.blessed_patterns).toEqual(['pattern-1', 'pattern-2', 'pattern-3']);
    });

    it('should create config with blessed pattern when file does not exist', async () => {
      mockDeps.access.mockRejectedValue(new Error('ENOENT'));
      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      const result = await blessPattern('/project', 'first-pattern');

      expect(result.blessed_patterns).toEqual(['first-pattern']);
      expect(mockDeps.writeFile).toHaveBeenCalled();
    });

    it('should preserve other config properties when blessing', async () => {
      const existingConfig = {
        blessed_patterns: [],
        always_review_paths: ['src/critical/'],
        query_count_thresholds: { relative_percent: 50, absolute_delta: 25 },
      };

      mockDeps.access.mockResolvedValue(undefined);
      mockDeps.readFile.mockResolvedValue(JSON.stringify(existingConfig));
      mockDeps.mkdir.mockResolvedValue(undefined);
      mockDeps.writeFile.mockResolvedValue(undefined);

      const result = await blessPattern('/project', 'new-pattern');

      expect(result.always_review_paths).toEqual(['src/critical/']);
      expect(result.query_count_thresholds).toEqual({
        relative_percent: 50,
        absolute_delta: 25,
      });
    });
  });
});
