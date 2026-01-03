from fastmcp import FastMCP
import spellbook_mcp.server as server
import json
from unittest.mock import patch
from pathlib import Path

def test_find_spellbook_skills_output(tmp_path):
    # Setup mock skills in a temp dir
    skill_dir = tmp_path / "skills" / "mock-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: mock-skill\ndescription: A mock skill\n---\n# Mock Content")

    # Patch get_skill_dirs to use our temp dir
    with patch('spellbook_mcp.server.get_skill_dirs', return_value=[tmp_path / "skills"]):
        # FastMCP tools wrap the function. Access underlying function via .fn (if available)
        # or just import the logic if we refactored.
        # Let's assume .fn works for FastMCP >= 0.1.0
        output = server.find_spellbook_skills.fn()
        
        # Verify it returns valid JSON
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['name'] == "mock-skill"
        assert data[0]['description'] == "A mock skill"

def test_use_spellbook_skill_output(tmp_path):
    # Setup mock skill
    skill_dir = tmp_path / "skills" / "mock-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: mock-skill\n---\n# Mock Content")

    with patch('spellbook_mcp.server.get_skill_dirs', return_value=[tmp_path / "skills"]):
        # Test success
        content = server.use_spellbook_skill.fn("mock-skill")
        assert "# Mock Content" in content
        
        # Test failure
        error_msg = server.use_spellbook_skill.fn("non-existent")
        assert "Error: Skill 'non-existent' not found" in error_msg

