# DACPAC Analyzer Skill

An [Agent Skill](https://agentskills.io) that analyzes SQL Server `.dacpac` and `.bacpac` package files. It extracts and presents tables, views, stored procedures, functions, constraints, indexes, schemas, sequences, roles, permissions, and all SQL body scripts.

## Installation

### Copilot CLI / Claude Code

Register this repo as a plugin marketplace:

```
/plugin marketplace add <owner>/dacpac-analyzer-skill
```

Then install the plugin:

```
/plugin install dacpac-analyzer@dacpac-analyzer-marketplace
```

### Manual

Copy the `skills/dacpac-analyzer/` directory into your agent's skills location.

## What It Does

Given a `.dacpac` or `.bacpac` file, this skill enables an agent to:

- **Document** a database schema: tables, columns, views, procedures, functions
- **Audit** constraints: primary keys, foreign keys, unique, check, defaults
- **Review** indexing strategy across all tables
- **Extract** all SQL body scripts from views, procedures, and functions
- **Search** across all named objects and columns

## Requirements

- Python 3.10+
- No external dependencies (pure Python standard library)

## Development

```bash
# Run tests
pip install pytest
pytest tests/ -q

# Run a command manually
python skills/dacpac-analyzer/scripts/analyze.py <path-to.dacpac> overview
```

## License

MIT
