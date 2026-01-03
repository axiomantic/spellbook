from pathlib import Path
from typing import List, Dict, Optional

def parse_frontmatter(content: str) -> Dict[str, str]:
    """
    Manually parse YAML frontmatter to avoid heavy dependencies.
    """
    lines = content.split('\n')
    metadata = {}
    in_frontmatter = False
    
    for line in lines:
        stripped = line.strip()
        if stripped == '---':
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
            
        if in_frontmatter:
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip().strip('"').strip("'")
                
    return metadata

def strip_frontmatter(content: str) -> str:
    """
    Remove YAML frontmatter from content.
    """
    lines = content.split('\n')
    in_frontmatter = False
    frontmatter_ended = False
    content_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped == '---':
            if in_frontmatter:
                frontmatter_ended = True
                continue
            in_frontmatter = True
            continue
            
        if frontmatter_ended or not in_frontmatter:
            content_lines.append(line)
            
    return '\n'.join(content_lines).strip()

def find_skills(search_dirs: List[Path]) -> List[Dict]:
    """
    Scan directories for SKILL.md files and return metadata.
    Handles shadowing: earlier dirs in search_dirs take precedence.
    """
    skills_map = {} # name -> metadata
    
    # Iterate in reverse order so higher priority (earlier in list) overwrites lower
    for search_dir in reversed(search_dirs):
        if not search_dir.exists():
            continue
            
        # Recursive glob for SKILL.md
        for skill_file in search_dir.rglob('SKILL.md'):
            try:
                content = skill_file.read_text(encoding='utf-8')
                metadata = parse_frontmatter(content)
                name = metadata.get('name')
                
                if name:
                    skills_map[name] = {
                        'name': name,
                        'description': metadata.get('description', ''),
                        'path': str(skill_file),
                        'source_type': 'custom' # simplified for now
                    }
            except Exception:
                continue
                
    return list(skills_map.values())

def load_skill(name: str, search_dirs: List[Path]) -> str:
    """
    Find and load a skill's content by name.
    """
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        for skill_file in search_dir.rglob('SKILL.md'):
            try:
                content = skill_file.read_text(encoding='utf-8')
                metadata = parse_frontmatter(content)
                if metadata.get('name') == name:
                    return strip_frontmatter(content)
            except Exception:
                continue
                
    raise ValueError(f"Skill '{name}' not found")
