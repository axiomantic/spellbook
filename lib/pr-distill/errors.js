/**
 * Error codes for PR distillation operations.
 * @readonly
 * @enum {string}
 */
const ErrorCode = {
  GH_NOT_AUTHENTICATED: 'GH_NOT_AUTHENTICATED',
  GH_PR_NOT_FOUND: 'GH_PR_NOT_FOUND',
  GH_RATE_LIMITED: 'GH_RATE_LIMITED',
  GH_NETWORK_ERROR: 'GH_NETWORK_ERROR',
  GH_VERSION_TOO_OLD: 'GH_VERSION_TOO_OLD',
  DIFF_PARSE_ERROR: 'DIFF_PARSE_ERROR',
  BINARY_FILE: 'BINARY_FILE',
  AI_TIMEOUT: 'AI_TIMEOUT',
  AI_PARSE_ERROR: 'AI_PARSE_ERROR',
  CONFIG_MISSING: 'CONFIG_MISSING',
  CONFIG_INVALID: 'CONFIG_INVALID',
  CACHE_CORRUPTED: 'CACHE_CORRUPTED',
  CACHE_NOT_FOUND: 'CACHE_NOT_FOUND',
};

/**
 * Structured error for PR distillation.
 */
class PRDistillError extends Error {
  /**
   * @param {ErrorCode} code
   * @param {string} message
   * @param {boolean} recoverable
   * @param {Object} [context]
   */
  constructor(code, message, recoverable, context = null) {
    super(message);
    this.name = 'PRDistillError';
    this.code = code;
    this.recoverable = recoverable;
    this.context = context;
  }

  userMessage() {
    return `[${this.code}] ${this.message}`;
  }
}

/**
 * Retry decorator for operations with exponential backoff.
 * @param {Object} options
 * @param {number} [options.maxAttempts=3]
 * @param {number} [options.backoffBase=1000] - Base delay in ms
 * @param {Set<ErrorCode>} [options.retryableCodes]
 */
function withRetry({
  maxAttempts = 3,
  backoffBase = 1000,
  retryableCodes = new Set([ErrorCode.GH_RATE_LIMITED, ErrorCode.GH_NETWORK_ERROR]),
} = {}) {
  return function decorator(fn) {
    return async function wrapper(...args) {
      let lastError;
      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
          return await fn(...args);
        } catch (e) {
          lastError = e;
          if (!(e instanceof PRDistillError) || !retryableCodes.has(e.code)) {
            throw e;
          }
          if (attempt < maxAttempts - 1) {
            const waitTime = backoffBase * Math.pow(2, attempt);  // 1s, 2s, 4s
            console.log(`${e.userMessage()} Retrying in ${waitTime / 1000}s...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
          }
        }
      }
      throw lastError;
    };
  };
}

module.exports = { ErrorCode, PRDistillError, withRetry };
