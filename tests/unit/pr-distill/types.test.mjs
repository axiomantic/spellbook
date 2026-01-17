import { describe, it, expect } from 'vitest';

// Import the types module - it only exports an empty object since it's JSDoc types only
import types from '../../../lib/pr-distill/types.js';

describe('types.js', () => {
  it('should load without error', () => {
    // The module should be importable
    expect(types).toBeDefined();
  });

  it('should export an empty object (types are JSDoc only)', () => {
    // types.js contains only JSDoc type definitions, no runtime exports
    expect(types).toEqual({});
  });
});
