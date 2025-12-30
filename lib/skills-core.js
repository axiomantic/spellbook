/**
 * Spellbook Skills Core Library
 *
 * Shared module for skill discovery and loading across Claude Code, OpenCode, and Codex.
 * This module is imported by platform-specific plugins/scripts.
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

/**
 * Extract YAML frontmatter from a skill file.
 *
 * @param {string} filePath - Path to SKILL.md file
 * @returns {{name: string, description: string}}
 */
function extractFrontmatter(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf8');
        const lines = content.split('\n');

        let inFrontmatter = false;
        let name = '';
        let description = '';

        for (const line of lines) {
            if (line.trim() === '---') {
                if (inFrontmatter) break;
                inFrontmatter = true;
                continue;
            }

            if (inFrontmatter) {
                const match = line.match(/^(\w+):\s*(.*)$/);
                if (match) {
                    const [, key, value] = match;
                    switch (key) {
                        case 'name':
                            name = value.trim();
                            break;
                        case 'description':
                            description = value.trim();
                            break;
                    }
                }
            }
        }

        return { name, description };
    } catch (error) {
        return { name: '', description: '' };
    }
}

/**
 * Find all SKILL.md files in a directory recursively.
 *
 * @param {string} dir - Directory to search
 * @param {string} sourceType - 'personal', 'spellbook', or 'superpowers' for namespacing
 * @param {number} maxDepth - Maximum recursion depth (default: 3)
 * @returns {Array<{path: string, name: string, description: string, sourceType: string}>}
 */
function findSkillsInDir(dir, sourceType, maxDepth = 3) {
    const skills = [];

    if (!fs.existsSync(dir)) return skills;

    function recurse(currentDir, depth) {
        if (depth > maxDepth) return;

        const entries = fs.readdirSync(currentDir, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(currentDir, entry.name);

            if (entry.isDirectory()) {
                // Check for SKILL.md in this directory
                const skillFile = path.join(fullPath, 'SKILL.md');
                if (fs.existsSync(skillFile)) {
                    const { name, description } = extractFrontmatter(skillFile);
                    skills.push({
                        path: fullPath,
                        skillFile: skillFile,
                        name: name || entry.name,
                        description: description || '',
                        sourceType: sourceType
                    });
                }

                // Recurse into subdirectories
                recurse(fullPath, depth + 1);
            }
        }
    }

    recurse(dir, 0);
    return skills;
}

/**
 * Resolve a skill name to its file path, handling shadowing.
 * Priority: personal > spellbook > superpowers
 *
 * @param {string} skillName - Name like "async-await-patterns" or "spellbook:my-skill"
 * @param {string} spellbookDir - Path to spellbook skills directory
 * @param {string} personalDir - Path to personal skills directory
 * @param {string} superpowersDir - Path to superpowers skills directory (optional)
 * @returns {{skillFile: string, sourceType: string, skillPath: string} | null}
 */
function resolveSkillPath(skillName, spellbookDir, personalDir, superpowersDir = null) {
    // Handle prefixes
    const forceSpellbook = skillName.startsWith('spellbook:');
    const forceSuperpowers = skillName.startsWith('superpowers:');

    let actualSkillName = skillName;
    if (forceSpellbook) actualSkillName = skillName.replace(/^spellbook:/, '');
    if (forceSuperpowers) actualSkillName = skillName.replace(/^superpowers:/, '');

    // Try personal skills first (unless explicitly namespaced)
    if (!forceSpellbook && !forceSuperpowers && personalDir) {
        const personalPath = path.join(personalDir, actualSkillName);
        const personalSkillFile = path.join(personalPath, 'SKILL.md');
        if (fs.existsSync(personalSkillFile)) {
            return {
                skillFile: personalSkillFile,
                sourceType: 'personal',
                skillPath: actualSkillName
            };
        }
    }

    // Try spellbook skills
    if (!forceSuperpowers && spellbookDir) {
        const spellbookPath = path.join(spellbookDir, actualSkillName);
        const spellbookSkillFile = path.join(spellbookPath, 'SKILL.md');
        if (fs.existsSync(spellbookSkillFile)) {
            return {
                skillFile: spellbookSkillFile,
                sourceType: 'spellbook',
                skillPath: actualSkillName
            };
        }
    }

    // Try superpowers skills (if directory provided)
    if (superpowersDir) {
        const superpowersPath = path.join(superpowersDir, actualSkillName);
        const superpowersSkillFile = path.join(superpowersPath, 'SKILL.md');
        if (fs.existsSync(superpowersSkillFile)) {
            return {
                skillFile: superpowersSkillFile,
                sourceType: 'superpowers',
                skillPath: actualSkillName
            };
        }
    }

    return null;
}

/**
 * Check if a git repository has updates available.
 *
 * @param {string} repoDir - Path to git repository
 * @returns {boolean} - True if updates are available
 */
function checkForUpdates(repoDir) {
    try {
        // Quick check with 3 second timeout to avoid delays if network is down
        const output = execSync('git fetch origin && git status --porcelain=v1 --branch', {
            cwd: repoDir,
            timeout: 3000,
            encoding: 'utf8',
            stdio: 'pipe'
        });

        // Parse git status output to see if we're behind
        const statusLines = output.split('\n');
        for (const line of statusLines) {
            if (line.startsWith('## ') && line.includes('[behind ')) {
                return true; // We're behind remote
            }
        }
        return false; // Up to date
    } catch (error) {
        // Network down, git error, timeout, etc. - don't block bootstrap
        return false;
    }
}

/**
 * Strip YAML frontmatter from skill content, returning just the content.
 *
 * @param {string} content - Full content including frontmatter
 * @returns {string} - Content without frontmatter
 */
function stripFrontmatter(content) {
    const lines = content.split('\n');
    let inFrontmatter = false;
    let frontmatterEnded = false;
    const contentLines = [];

    for (const line of lines) {
        if (line.trim() === '---') {
            if (inFrontmatter) {
                frontmatterEnded = true;
                continue;
            }
            inFrontmatter = true;
            continue;
        }

        if (frontmatterEnded || !inFrontmatter) {
            contentLines.push(line);
        }
    }

    return contentLines.join('\n').trim();
}

export {
    extractFrontmatter,
    findSkillsInDir,
    resolveSkillPath,
    checkForUpdates,
    stripFrontmatter
};
