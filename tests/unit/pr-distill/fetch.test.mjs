import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ErrorCode, PRDistillError } from '../../../lib/pr-distill/errors.js';
import {
  checkGhVersion,
  parsePRIdentifier,
  fetchPR,
  setExecutor,
  resetExecutor,
  compareSemver,
} from '../../../lib/pr-distill/fetch.js';

describe('compareSemver', () => {
  it('should return 0 for equal versions', () => {
    expect(compareSemver('1.0.0', '1.0.0')).toBe(0);
    expect(compareSemver('2.30.0', '2.30.0')).toBe(0);
  });

  it('should return -1 when first version is lower', () => {
    expect(compareSemver('1.0.0', '2.0.0')).toBe(-1);
    expect(compareSemver('2.29.0', '2.30.0')).toBe(-1);
    expect(compareSemver('2.30.0', '2.30.1')).toBe(-1);
  });

  it('should return 1 when first version is higher', () => {
    expect(compareSemver('2.0.0', '1.0.0')).toBe(1);
    expect(compareSemver('2.31.0', '2.30.0')).toBe(1);
    expect(compareSemver('3.0.0', '2.30.0')).toBe(1);
  });
});

describe('checkGhVersion', () => {
  let mockExecutor;

  beforeEach(() => {
    mockExecutor = vi.fn();
    setExecutor(mockExecutor);
  });

  afterEach(() => {
    resetExecutor();
  });

  it('should return true for gh version 2.30.0', () => {
    mockExecutor.mockReturnValue('gh version 2.30.0 (2023-05-10)\n');

    expect(checkGhVersion()).toBe(true);
  });

  it('should return true for gh version 2.31.0 (higher than minimum)', () => {
    mockExecutor.mockReturnValue('gh version 2.31.0 (2023-06-15)\n');

    expect(checkGhVersion()).toBe(true);
  });

  it('should return true for gh version 3.0.0 (major version higher)', () => {
    mockExecutor.mockReturnValue('gh version 3.0.0 (2024-01-01)\n');

    expect(checkGhVersion()).toBe(true);
  });

  it('should throw GH_VERSION_TOO_OLD for version 2.29.0', () => {
    mockExecutor.mockReturnValue('gh version 2.29.0 (2023-04-01)\n');

    let caughtError = null;
    try {
      checkGhVersion();
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_VERSION_TOO_OLD);
    expect(caughtError.recoverable).toBe(false);
  });

  it('should throw GH_VERSION_TOO_OLD for version 1.14.0', () => {
    mockExecutor.mockReturnValue('gh version 1.14.0 (2022-01-01)\n');

    let caughtError = null;
    try {
      checkGhVersion();
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_VERSION_TOO_OLD);
  });

  it('should throw GH_NOT_AUTHENTICATED when gh is not installed', () => {
    mockExecutor.mockImplementation(() => {
      const error = new Error('command not found: gh');
      error.status = 127;
      throw error;
    });

    let caughtError = null;
    try {
      checkGhVersion();
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_NOT_AUTHENTICATED);
    expect(caughtError.recoverable).toBe(false);
  });
});

describe('parsePRIdentifier', () => {
  let mockExecutor;

  beforeEach(() => {
    mockExecutor = vi.fn();
    setExecutor(mockExecutor);
  });

  afterEach(() => {
    resetExecutor();
  });

  it('should parse a plain PR number with repo from git remote', () => {
    mockExecutor.mockReturnValue('https://github.com/owner/repo.git\n');

    const result = parsePRIdentifier('123');

    expect(result).toEqual({
      prNumber: 123,
      repo: 'owner/repo',
    });
  });

  it('should parse a plain PR number with SSH git remote', () => {
    mockExecutor.mockReturnValue('git@github.com:owner/repo.git\n');

    const result = parsePRIdentifier('456');

    expect(result).toEqual({
      prNumber: 456,
      repo: 'owner/repo',
    });
  });

  it('should parse a GitHub PR URL', () => {
    const result = parsePRIdentifier('https://github.com/owner/repo/pull/789');

    expect(result).toEqual({
      prNumber: 789,
      repo: 'owner/repo',
    });
    // Should not call executor for URL
    expect(mockExecutor).not.toHaveBeenCalled();
  });

  it('should parse a GitHub PR URL with trailing slash', () => {
    const result = parsePRIdentifier('https://github.com/owner/repo/pull/101/');

    expect(result).toEqual({
      prNumber: 101,
      repo: 'owner/repo',
    });
  });

  it('should parse a GitHub PR URL with additional path components', () => {
    const result = parsePRIdentifier('https://github.com/owner/repo/pull/202/files');

    expect(result).toEqual({
      prNumber: 202,
      repo: 'owner/repo',
    });
  });

  it('should handle hyphenated repo names in URL', () => {
    const result = parsePRIdentifier('https://github.com/my-org/my-awesome-repo/pull/303');

    expect(result).toEqual({
      prNumber: 303,
      repo: 'my-org/my-awesome-repo',
    });
  });

  it('should throw GH_PR_NOT_FOUND for invalid PR identifier', () => {
    let caughtError = null;
    try {
      parsePRIdentifier('not-a-pr');
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_PR_NOT_FOUND);
  });

  it('should throw GH_PR_NOT_FOUND when git remote fails', () => {
    mockExecutor.mockImplementation(() => {
      throw new Error('Not a git repository');
    });

    let caughtError = null;
    try {
      parsePRIdentifier('123');
    } catch (e) {
      caughtError = e;
    }
    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_PR_NOT_FOUND);
    expect(caughtError.message).toContain('Could not determine repository');
  });
});

describe('fetchPR', () => {
  let mockExecutor;

  beforeEach(() => {
    mockExecutor = vi.fn();
    setExecutor(mockExecutor);
  });

  afterEach(() => {
    resetExecutor();
  });

  it('should fetch PR metadata and diff', async () => {
    const mockMeta = {
      number: 123,
      title: 'Fix bug',
      body: 'This fixes the bug',
      headRefOid: 'abc123',
      baseRefName: 'main',
      additions: 10,
      deletions: 5,
      files: [
        { path: 'src/index.js', additions: 5, deletions: 2 },
        { path: 'src/utils.js', additions: 5, deletions: 3 },
      ],
    };
    const mockDiff = `diff --git a/src/index.js b/src/index.js
index abc123..def456 100644
--- a/src/index.js
+++ b/src/index.js
@@ -1,3 +1,5 @@
+// New comment
 function test() {
-  return 1;
+  return 2;
 }
`;

    mockExecutor
      // First call for gh version check
      .mockReturnValueOnce('gh version 2.30.0\n')
      // Second call for pr view (metadata)
      .mockReturnValueOnce(JSON.stringify(mockMeta))
      // Third call for pr diff
      .mockReturnValueOnce(mockDiff);

    const result = await fetchPR({ prNumber: 123, repo: 'owner/repo' });

    expect(result.meta).toEqual(mockMeta);
    expect(result.diff).toBe(mockDiff);
    expect(result.repo).toBe('owner/repo');
  });

  it('should throw GH_PR_NOT_FOUND when PR does not exist', async () => {
    mockExecutor.mockReturnValueOnce('gh version 2.30.0\n');
    mockExecutor.mockImplementationOnce(() => {
      const error = new Error('Could not resolve to a PullRequest');
      error.stderr = Buffer.from('Could not resolve to a PullRequest');
      throw error;
    });

    let caughtError = null;
    try {
      await fetchPR({ prNumber: 99999, repo: 'owner/repo' });
    } catch (e) {
      caughtError = e;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_PR_NOT_FOUND);
    expect(caughtError.recoverable).toBe(false);
  });

  it('should throw GH_RATE_LIMITED when rate limited', async () => {
    mockExecutor.mockReturnValueOnce('gh version 2.30.0\n');
    mockExecutor.mockImplementationOnce(() => {
      const error = new Error('API rate limit exceeded');
      error.stderr = Buffer.from('rate limit');
      throw error;
    });

    let caughtError = null;
    try {
      await fetchPR({ prNumber: 123, repo: 'owner/repo' });
    } catch (e) {
      caughtError = e;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_RATE_LIMITED);
    expect(caughtError.recoverable).toBe(true);
  });

  it('should throw GH_NOT_AUTHENTICATED when not authenticated', async () => {
    mockExecutor.mockReturnValueOnce('gh version 2.30.0\n');
    mockExecutor.mockImplementationOnce(() => {
      const error = new Error('gh auth login');
      error.stderr = Buffer.from('not logged into any GitHub hosts');
      throw error;
    });

    let caughtError = null;
    try {
      await fetchPR({ prNumber: 123, repo: 'owner/repo' });
    } catch (e) {
      caughtError = e;
    }

    expect(caughtError).not.toBeNull();
    expect(caughtError.name).toBe('PRDistillError');
    expect(caughtError.code).toBe(ErrorCode.GH_NOT_AUTHENTICATED);
    expect(caughtError.recoverable).toBe(false);
  });

  it('should return correct meta format with all required fields', async () => {
    const mockMeta = {
      number: 456,
      title: 'Add feature',
      body: 'New feature implementation',
      headRefOid: 'def789',
      baseRefName: 'develop',
      additions: 100,
      deletions: 20,
      files: [
        { path: 'src/feature.js', additions: 80, deletions: 10 },
        { path: 'tests/feature.test.js', additions: 20, deletions: 10 },
      ],
    };

    mockExecutor
      .mockReturnValueOnce('gh version 2.30.0\n')
      .mockReturnValueOnce(JSON.stringify(mockMeta))
      .mockReturnValueOnce('diff content');

    const result = await fetchPR({ prNumber: 456, repo: 'owner/repo' });

    expect(result.meta).toHaveProperty('number', 456);
    expect(result.meta).toHaveProperty('title', 'Add feature');
    expect(result.meta).toHaveProperty('body', 'New feature implementation');
    expect(result.meta).toHaveProperty('headRefOid', 'def789');
    expect(result.meta).toHaveProperty('baseRefName', 'develop');
    expect(result.meta).toHaveProperty('additions', 100);
    expect(result.meta).toHaveProperty('deletions', 20);
    expect(result.meta).toHaveProperty('files');
    expect(result.meta.files).toHaveLength(2);
  });
});
