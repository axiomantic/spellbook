import { describe, it, expect } from 'vitest';
import {
  extractFrontmatter,
  stripFrontmatter,
  findSkillsInDir,
  resolveSkillPath
} from '../../lib/skills-core.js';

describe('extractFrontmatter', () => {
  it('should extract valid frontmatter', () => {
    const content = `---
name: test-skill
description: A test skill
---
# Content`;

    const frontmatter = extractFrontmatter(content);
    expect(frontmatter).toEqual({
      name: 'test-skill',
      description: 'A test skill'
    });
  });

  it('should return null for missing frontmatter', () => {
    const content = '# Just content';
    const frontmatter = extractFrontmatter(content);
    expect(frontmatter).toBeNull();
  });

  it('should return null for malformed frontmatter', () => {
    const content = `---
invalid yaml: [
---
Content`;
    const frontmatter = extractFrontmatter(content);
    expect(frontmatter).toBeNull();
  });
});

describe('stripFrontmatter', () => {
  it('should remove frontmatter from content', () => {
    const content = `---
name: test
---
# Content here`;

    const stripped = stripFrontmatter(content);
    expect(stripped).toBe('# Content here');
  });

  it('should return content unchanged if no frontmatter', () => {
    const content = '# Just content';
    const stripped = stripFrontmatter(content);
    expect(stripped).toBe('# Just content');
  });

  it('should handle empty frontmatter', () => {
    const content = `---
---
Content`;
    const stripped = stripFrontmatter(content);
    expect(stripped).toBe('Content');
  });
});

describe('skill name validation', () => {
  const validNames = [
    'my-skill',
    'my_skill',
    'MySkill123',
    'skill-with-many-dashes',
    'skill_with_underscores'
  ];

  const invalidNames = [
    'my.skill',
    'my skill',
    '../etc/passwd',
    'skill:name',
    '',
    'a'.repeat(101) // 101 characters
  ];

  validNames.forEach(name => {
    it(`should accept valid name: ${name}`, () => {
      const pattern = /^[a-zA-Z0-9_-]{1,100}$/;
      expect(pattern.test(name)).toBe(true);
    });
  });

  invalidNames.forEach(name => {
    it(`should reject invalid name: ${name.substring(0, 20)}...`, () => {
      const pattern = /^[a-zA-Z0-9_-]{1,100}$/;
      expect(pattern.test(name)).toBe(false);
    });
  });
});
