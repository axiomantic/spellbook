/**
 * Spellbook plugin for OpenCode.ai
 *
 * Provides custom tools for loading and discovering skills from spellbook.
 * Spellbook includes core workflow skills (from obra/superpowers) plus
 * domain-specific extensions.
 */

import path from 'path';
import fs from 'fs';
import os from 'os';
import { fileURLToPath } from 'url';
import { tool } from '@opencode-ai/plugin/tool';
import * as skillsCore from '../../lib/skills-core.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const SpellbookPlugin = async ({ client, directory }) => {
  const homeDir = os.homedir();
  const projectSkillsDir = path.join(directory, '.opencode/skills');

  // Derive spellbook skills dir from plugin location
  const spellbookSkillsDir = path.resolve(__dirname, '../../skills');
  const personalSkillsDir = path.join(homeDir, '.config/opencode/skills');

  // Claude config skills (from CLAUDE_CONFIG_DIR)
  const claudeConfigDir = process.env.CLAUDE_CONFIG_DIR || path.join(homeDir, '.claude');
  const claudeSkillsDir = path.join(claudeConfigDir, 'skills');

  // Helper to generate bootstrap content
  const getBootstrapContent = (compact = false) => {
    const toolMapping = compact
      ? `**Tool Mapping:** TodoWrite->update_plan, Task->@mention, Skill->use_spellbook_skill

**Skills naming (priority):** project: > personal > spellbook: > claude:`
      : `**Tool Mapping for OpenCode:**
When skills reference tools you don't have, substitute OpenCode equivalents:
- \`TodoWrite\` → \`update_plan\`
- \`Task\` tool with subagents → Use OpenCode's subagent system (@mention)
- \`Skill\` tool → \`use_spellbook_skill\` custom tool
- \`Read\`, \`Write\`, \`Edit\`, \`Bash\` → Your native tools

**Skills naming (priority order):**
- Project skills: \`project:skill-name\` (in .opencode/skills/)
- Personal skills: \`skill-name\` (in ~/.config/opencode/skills/)
- Spellbook skills: \`spellbook:skill-name\` (from spellbook repo)
- Claude skills: \`claude:skill-name\` (from $CLAUDE_CONFIG_DIR/skills/)`;

    return `<SPELLBOOK_CONTEXT>
You have access to spellbook skills - AI assistant workflows and patterns.

Spellbook includes core workflow skills (brainstorming, planning, debugging, TDD)
plus domain-specific skills like async-await-patterns, factchecker, green-mirage-audit,
scientific-debugging, and more.

${toolMapping}

Use \`find_spellbook_skills\` to see available skills.
Use \`use_spellbook_skill <name>\` to load and follow a skill.
</SPELLBOOK_CONTEXT>`;
  };

  // Helper to inject bootstrap via session.prompt
  const injectBootstrap = async (sessionID, compact = false) => {
    const bootstrapContent = getBootstrapContent(compact);

    try {
      await client.session.prompt({
        path: { id: sessionID },
        body: {
          noReply: true,
          parts: [{ type: "text", text: bootstrapContent, synthetic: true }]
        }
      });
      return true;
    } catch (err) {
      return false;
    }
  };

  return {
    tool: {
      use_spellbook_skill: tool({
        description: 'Load a skill from spellbook. Spellbook includes workflow and domain-specific skills.',
        args: {
          skill_name: tool.schema.string().describe('Name of the skill (e.g., "async-await-patterns", "spellbook:factchecker", "project:my-skill")')
        },
        execute: async (args, context) => {
          const { skill_name } = args;

          // Check for project: prefix
          const forceProject = skill_name.startsWith('project:');
          const actualSkillName = forceProject ? skill_name.replace(/^project:/, '') : skill_name;

          let resolved = null;

          // Try project skills first
          if (forceProject || !skill_name.includes(':')) {
            const projectPath = path.join(projectSkillsDir, actualSkillName);
            const projectSkillFile = path.join(projectPath, 'SKILL.md');
            if (fs.existsSync(projectSkillFile)) {
              resolved = {
                skillFile: projectSkillFile,
                sourceType: 'project',
                skillPath: actualSkillName
              };
            }
          }

          // Fall back to personal/spellbook/claude resolution
          if (!resolved && !forceProject) {
            resolved = skillsCore.resolveSkillPath(
              skill_name,
              spellbookSkillsDir,
              personalSkillsDir,
              fs.existsSync(claudeSkillsDir) ? claudeSkillsDir : null
            );
          }

          if (!resolved) {
            return `Error: Skill "${skill_name}" not found.\n\nRun find_spellbook_skills to see available skills.`;
          }

          const fullContent = fs.readFileSync(resolved.skillFile, 'utf8');
          const { name, description } = skillsCore.extractFrontmatter(resolved.skillFile);
          const content = skillsCore.stripFrontmatter(fullContent);
          const skillDirectory = path.dirname(resolved.skillFile);

          const skillHeader = `# ${name || skill_name}
# ${description || ''}
# Source: ${resolved.sourceType}
# Supporting files: ${skillDirectory}
# ============================================`;

          // Insert as user message for persistence
          try {
            await client.session.prompt({
              path: { id: context.sessionID },
              body: {
                noReply: true,
                parts: [
                  { type: "text", text: `Loading skill: ${name || skill_name}`, synthetic: true },
                  { type: "text", text: `${skillHeader}\n\n${content}`, synthetic: true }
                ]
              }
            });
          } catch (err) {
            return `${skillHeader}\n\n${content}`;
          }

          return `Launching skill: ${name || skill_name}`;
        }
      }),

      find_spellbook_skills: tool({
        description: 'List all available skills from project, personal, spellbook, and claude libraries.',
        args: {},
        execute: async (args, context) => {
          const projectSkills = skillsCore.findSkillsInDir(projectSkillsDir, 'project', 3);
          const personalSkills = skillsCore.findSkillsInDir(personalSkillsDir, 'personal', 3);
          const spellbookSkills = skillsCore.findSkillsInDir(spellbookSkillsDir, 'spellbook', 3);

          let claudeSkills = [];
          if (fs.existsSync(claudeSkillsDir)) {
            claudeSkills = skillsCore.findSkillsInDir(claudeSkillsDir, 'claude', 3);
          }

          const allSkills = [...projectSkills, ...personalSkills, ...spellbookSkills, ...claudeSkills];

          if (allSkills.length === 0) {
            return 'No skills found. Check installation of spellbook.';
          }

          let output = 'Available skills:\n\n';

          for (const skill of allSkills) {
            let namespace;
            switch (skill.sourceType) {
              case 'project': namespace = 'project:'; break;
              case 'personal': namespace = ''; break;
              case 'spellbook': namespace = 'spellbook:'; break;
              default: namespace = 'claude:';
            }

            output += `${namespace}${skill.name}\n`;
            if (skill.description) {
              output += `  ${skill.description}\n`;
            }
            output += `  Directory: ${skill.path}\n\n`;
          }

          return output;
        }
      })
    },

    event: async ({ event }) => {
      const getSessionID = () => {
        return event.properties?.info?.id ||
          event.properties?.sessionID ||
          event.session?.id;
      };

      // Inject bootstrap at session creation
      if (event.type === 'session.created') {
        const sessionID = getSessionID();
        if (sessionID) {
          await injectBootstrap(sessionID, false);
        }
      }

      // Re-inject after compaction
      if (event.type === 'session.compacted') {
        const sessionID = getSessionID();
        if (sessionID) {
          await injectBootstrap(sessionID, true);
        }
      }
    }
  };
};
