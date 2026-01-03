
import pytest
from pathlib import Path
from spellbook_mcp.skill_ops import find_skills, load_skill

def test_find_skills(tmp_path):
    # Setup mock skills
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: Test skill\n---\n# Content")
    
    # Create another skill without description to test fallback
    skill_dir2 = tmp_path / "skills" / "other-skill"
    skill_dir2.mkdir(parents=True)
    (skill_dir2 / "SKILL.md").write_text("---\nname: other-skill\n---\n# Content")
    
    skills = find_skills([tmp_path / "skills"])
    # Sort by name to ensure consistent order for assertion
    skills.sort(key=lambda x: x['name'])
    
    assert len(skills) == 2
    assert skills[0]['name'] == "my-skill"
    assert skills[0]['description'] == "Test skill"
    assert skills[1]['name'] == "other-skill"
    assert skills[1]['description'] == ""

def test_load_skill(tmp_path):
    # Setup mock skill
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# Real Content")
    
    content = load_skill("my-skill", search_dirs=[tmp_path / "skills"])
    assert "# Real Content" in content
    assert "---" not in content

def test_load_skill_shadowing(tmp_path):
    # Setup primary and secondary dirs
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    
    (primary / "skill-a" / "SKILL.md").parent.mkdir(parents=True)
    (primary / "skill-a" / "SKILL.md").write_text("---\nname: skill-a\n---\n# Primary Content")
    
    (secondary / "skill-a" / "SKILL.md").parent.mkdir(parents=True)
    (secondary / "skill-a" / "SKILL.md").write_text("---\nname: skill-a\n---\n# Secondary Content")
    
    # Should load from primary first
    content = load_skill("skill-a", search_dirs=[primary, secondary])
    assert "# Primary Content" in content
