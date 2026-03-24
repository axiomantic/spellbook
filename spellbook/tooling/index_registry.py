import json
import os
import sqlite3
import yaml
from pathlib import Path

def index_registry(yaml_path: str, db_path: str):
    """Convert YAML registry to SQLite DB for token-efficient searching."""
    if not os.path.exists(yaml_path):
        print(f"Error: {yaml_path} not found.")
        return

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    # Delete existing DB if it exists to ensure clean state
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            keywords TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id INTEGER,
            name TEXT,
            type TEXT,
            trust_tier INTEGER,
            source TEXT,
            description TEXT,
            mcp_tool_prefix TEXT,
            cli_names TEXT,
            dep_signals TEXT,
            risks TEXT,
            next_steps TEXT,
            FOREIGN KEY (domain_id) REFERENCES domains(id)
        )
    ''')

    domains = data.get('domains', {})
    for domain_name, domain_data in domains.items():
        keywords = ",".join(domain_data.get('keywords', []))
        cursor.execute('INSERT INTO domains (name, keywords) VALUES (?, ?)', (domain_name, keywords))
        domain_id = cursor.lastrowid

        for tool in domain_data.get('tools', []):
            cursor.execute('''
                INSERT INTO tools (
                    domain_id, name, type, trust_tier, source, description, 
                    mcp_tool_prefix, cli_names, dep_signals, risks, next_steps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                domain_id,
                tool.get('name'),
                tool.get('type'),
                tool.get('trust_tier'),
                tool.get('source'),
                tool.get('description'),
                tool.get('mcp_tool_prefix', ''),
                ",".join(tool.get('cli_names', [])),
                json.dumps(tool.get('dep_signals', {})),
                json.dumps(tool.get('risks', [])),
                json.dumps(tool.get('next_steps', []))
            ))

    conn.commit()
    conn.close()
    print(f"Successfully indexed registry to {db_path}")

if __name__ == "__main__":
    import json
    base_dir = Path(__file__).parent.parent
    yaml_file = base_dir / "data" / "tooling-registry.yaml"
    db_file = base_dir / "data" / "tooling-registry.db"
    index_registry(str(yaml_file), str(db_file))
