import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';
import {
  extractFrontmatter,
  stripFrontmatter,
  findSkillsInDir,
  resolveSkillPath
} from '../../lib/skills-core.js';

// Create temp directory for test files
let tempDir;

beforeAll(() => {
  tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'spellbook-test-'));
});

afterAll(() => {
  // Clean up temp directory
  fs.rmSync(tempDir, { recursive: true, force: true });
});

function createTempFile(name, content) {
  const filePath = path.join(tempDir, name);
  fs.writeFileSync(filePath, content);
  return filePath;
}

describe('extractFrontmatter', () => {
  it('should extract valid frontmatter from file', () => {
    const content = `---
name: test-skill
description: A test skill
---
# Content`;

    const filePath = createTempFile('valid-skill.md', content);
    const frontmatter = extractFrontmatter(filePath);
    expect(frontmatter.name).toBe('test-skill');
    expect(frontmatter.description).toBe('A test skill');
  });

  it('should return empty strings for missing frontmatter', () => {
    const content = '# Just content';
    const filePath = createTempFile('no-frontmatter.md', content);
    const frontmatter = extractFrontmatter(filePath);
    expect(frontmatter.name).toBe('');
    expect(frontmatter.description).toBe('');
  });

  it('should return empty strings for malformed frontmatter', () => {
    const content = `---
invalid yaml: [
---
Content`;
    const filePath = createTempFile('malformed.md', content);
    const frontmatter = extractFrontmatter(filePath);
    expect(frontmatter.name).toBe('');
    expect(frontmatter.description).toBe('');
  });

  it('should return empty strings for non-existent file', () => {
    const frontmatter = extractFrontmatter('/nonexistent/file.md');
    expect(frontmatter.name).toBe('');
    expect(frontmatter.description).toBe('');
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

describe('findSkillsInDir', () => {
  it('should find skills in directory', () => {
    // Create a skill directory structure
    const skillDir = path.join(tempDir, 'skills', 'my-skill');
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(path.join(skillDir, 'SKILL.md'), `---
name: my-skill
description: A test skill for testing
---
# My Skill`);

    const skills = findSkillsInDir(path.join(tempDir, 'skills'), 'test');
    expect(skills.length).toBe(1);
    expect(skills[0].name).toBe('my-skill');
    expect(skills[0].sourceType).toBe('test');
  });

  it('should return empty array for non-existent directory', () => {
    const skills = findSkillsInDir('/nonexistent/dir', 'test');
    expect(skills).toEqual([]);
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
