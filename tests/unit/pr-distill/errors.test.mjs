import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We'll import from the module we're about to create
import { ErrorCode, PRDistillError, withRetry } from '../../../lib/pr-distill/errors.js';

describe('ErrorCode', () => {
  it('should define GH_NOT_AUTHENTICATED code', () => {
    expect(ErrorCode.GH_NOT_AUTHENTICATED).toBe('GH_NOT_AUTHENTICATED');
  });

  it('should define GH_PR_NOT_FOUND code', () => {
    expect(ErrorCode.GH_PR_NOT_FOUND).toBe('GH_PR_NOT_FOUND');
  });

  it('should define GH_RATE_LIMITED code', () => {
    expect(ErrorCode.GH_RATE_LIMITED).toBe('GH_RATE_LIMITED');
  });

  it('should define GH_NETWORK_ERROR code', () => {
    expect(ErrorCode.GH_NETWORK_ERROR).toBe('GH_NETWORK_ERROR');
  });

  it('should define GH_VERSION_TOO_OLD code', () => {
    expect(ErrorCode.GH_VERSION_TOO_OLD).toBe('GH_VERSION_TOO_OLD');
  });

  it('should define DIFF_PARSE_ERROR code', () => {
    expect(ErrorCode.DIFF_PARSE_ERROR).toBe('DIFF_PARSE_ERROR');
  });

  it('should define BINARY_FILE code', () => {
    expect(ErrorCode.BINARY_FILE).toBe('BINARY_FILE');
  });

  it('should define AI_TIMEOUT code', () => {
    expect(ErrorCode.AI_TIMEOUT).toBe('AI_TIMEOUT');
  });

  it('should define AI_PARSE_ERROR code', () => {
    expect(ErrorCode.AI_PARSE_ERROR).toBe('AI_PARSE_ERROR');
  });

  it('should define CONFIG_MISSING code', () => {
    expect(ErrorCode.CONFIG_MISSING).toBe('CONFIG_MISSING');
  });

  it('should define CONFIG_INVALID code', () => {
    expect(ErrorCode.CONFIG_INVALID).toBe('CONFIG_INVALID');
  });

  it('should define CACHE_CORRUPTED code', () => {
    expect(ErrorCode.CACHE_CORRUPTED).toBe('CACHE_CORRUPTED');
  });
});

describe('PRDistillError', () => {
  it('should create error with code, message, and recoverable flag', () => {
    const error = new PRDistillError(
      ErrorCode.GH_PR_NOT_FOUND,
      'PR #123 not found',
      false
    );

    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(PRDistillError);
    expect(error.name).toBe('PRDistillError');
    expect(error.code).toBe('GH_PR_NOT_FOUND');
    expect(error.message).toBe('PR #123 not found');
    expect(error.recoverable).toBe(false);
    expect(error.context).toBeNull();
  });

  it('should create error with optional context', () => {
    const context = { prNumber: 123, repo: 'owner/repo' };
    const error = new PRDistillError(
      ErrorCode.GH_NETWORK_ERROR,
      'Network timeout',
      true,
      context
    );

    expect(error.context).toEqual(context);
  });

  it('should format userMessage correctly', () => {
    const error = new PRDistillError(
      ErrorCode.GH_RATE_LIMITED,
      'Rate limit exceeded',
      true
    );

    expect(error.userMessage()).toBe('[GH_RATE_LIMITED] Rate limit exceeded');
  });
});

describe('withRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should return result on first success', async () => {
    const fn = vi.fn().mockResolvedValue('success');
    const retryFn = withRetry()(fn);

    const result = await retryFn('arg1', 'arg2');

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('arg1', 'arg2');
  });

  it('should retry on retryable PRDistillError', async () => {
    const retryableError = new PRDistillError(
      ErrorCode.GH_RATE_LIMITED,
      'Rate limited',
      true
    );
    const fn = vi.fn()
      .mockRejectedValueOnce(retryableError)
      .mockRejectedValueOnce(retryableError)
      .mockResolvedValue('success');

    const retryFn = withRetry({ maxAttempts: 3, backoffBase: 1000 })(fn);

    const resultPromise = retryFn();

    // First attempt fails, wait for backoff
    await vi.advanceTimersByTimeAsync(1000);

    // Second attempt fails, wait for backoff (2s exponential)
    await vi.advanceTimersByTimeAsync(2000);

    // Third attempt succeeds
    const result = await resultPromise;

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('should throw immediately on non-retryable PRDistillError', async () => {
    const nonRetryableError = new PRDistillError(
      ErrorCode.GH_PR_NOT_FOUND,
      'PR not found',
      false
    );
    const fn = vi.fn().mockRejectedValue(nonRetryableError);

    const retryFn = withRetry({ maxAttempts: 3 })(fn);

    await expect(retryFn()).rejects.toThrow(nonRetryableError);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('should throw immediately on non-PRDistillError', async () => {
    const genericError = new Error('Generic error');
    const fn = vi.fn().mockRejectedValue(genericError);

    const retryFn = withRetry({ maxAttempts: 3 })(fn);

    await expect(retryFn()).rejects.toThrow(genericError);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('should throw after max attempts exhausted', async () => {
    const retryableError = new PRDistillError(
      ErrorCode.GH_NETWORK_ERROR,
      'Network error',
      true
    );
    const fn = vi.fn().mockRejectedValue(retryableError);

    // Suppress console.log during this test
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    const retryFn = withRetry({ maxAttempts: 3, backoffBase: 100 })(fn);

    // Wrap the promise to handle rejection properly
    let caughtError = null;
    const resultPromise = retryFn().catch(e => { caughtError = e; });

    // Advance through all retries
    await vi.advanceTimersByTimeAsync(100);  // First backoff
    await vi.advanceTimersByTimeAsync(200);  // Second backoff

    await resultPromise;
    expect(caughtError).toBe(retryableError);
    expect(fn).toHaveBeenCalledTimes(3);
    consoleSpy.mockRestore();
  });

  it('should use custom retryableCodes', async () => {
    const customRetryableError = new PRDistillError(
      ErrorCode.AI_TIMEOUT,
      'AI timed out',
      true
    );
    const fn = vi.fn()
      .mockRejectedValueOnce(customRetryableError)
      .mockResolvedValue('success');

    const retryFn = withRetry({
      maxAttempts: 2,
      backoffBase: 100,
      retryableCodes: new Set([ErrorCode.AI_TIMEOUT])
    })(fn);

    const resultPromise = retryFn();
    await vi.advanceTimersByTimeAsync(100);
    const result = await resultPromise;

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('should use exponential backoff (1s, 2s, 4s)', async () => {
    const error = new PRDistillError(ErrorCode.GH_RATE_LIMITED, 'limited', true);
    const fn = vi.fn().mockRejectedValue(error);

    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    const retryFn = withRetry({ maxAttempts: 4, backoffBase: 1000 })(fn);

    const resultPromise = retryFn().catch(() => {});

    // First backoff: 1000ms
    await vi.advanceTimersByTimeAsync(1000);
    expect(fn).toHaveBeenCalledTimes(2);

    // Second backoff: 2000ms
    await vi.advanceTimersByTimeAsync(2000);
    expect(fn).toHaveBeenCalledTimes(3);

    // Third backoff: 4000ms
    await vi.advanceTimersByTimeAsync(4000);
    expect(fn).toHaveBeenCalledTimes(4);

    await resultPromise;
    consoleSpy.mockRestore();
  });
});
