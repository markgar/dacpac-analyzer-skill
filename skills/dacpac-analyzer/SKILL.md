---
name: dacpac-analyzer
description: Analyze SQL Server .dacpac and .bacpac package files. Use when users need to understand, document, or audit a database schema captured in a DACPAC or BACPAC. Extracts tables, views, stored procedures, functions, constraints, indexes, schemas, sequences, table types, roles, permissions, and all SQL body scripts. Provides object-level detail including column types, nullability, parameters, foreign key relationships, and index definitions.
compatibility: Requires Python 3.10+. Uses only Python standard library (no pip install needed). Works with .dacpac (schema-only) and .bacpac (schema + data) files.
---

# DACPAC Analyzer

Analyze SQL Server `.dacpac` and `.bacpac` package files to extract and present complete database schema information.

## How it works

DACPAC and BACPAC files are ZIP archives containing:
- **model.xml** — complete SQL Server schema definition
- **DacMetadata.xml** — package name and version
- **Origin.xml** — server version, export timestamp, object counts

The analyzer extracts these files, parses the XML, and presents structured schema information via CLI commands.

## Usage

```
python scripts/analyze.py <path-to-dacpac-or-bacpac> <command> [args...]
```

## Commands

### Package-level

| Command | Description |
|---------|-------------|
| `overview` | Package metadata, origin info, and object counts |
| `summary` | High-level stats — counts per object type |

### Schema objects

| Command | Description |
|---------|-------------|
| `list-schemas` | All database schemas |
| `list-tables` | All tables with column counts |
| `table-detail <name>` | Full table — columns, types, nullability, constraints, indexes |
| `list-views` | All views with column counts |
| `view-detail <name>` | View columns and query script |
| `list-procedures` | All stored procedures |
| `procedure-detail <name>` | Procedure parameters, body script, dependencies |
| `list-functions` | All functions (scalar + inline TVF) |
| `function-detail <name>` | Function parameters, return type, body script |

### Constraints and indexes

| Command | Description |
|---------|-------------|
| `list-constraints` | All PKs, FKs, unique, check, and default constraints |
| `list-indexes` | All indexes with columns and type |

### Other objects

| Command | Description |
|---------|-------------|
| `list-sequences` | All sequences with type, start, increment |
| `list-table-types` | All user-defined table types |
| `list-roles` | All database roles |
| `list-permissions` | All permission statements |

### Extraction and search

| Command | Description |
|---------|-------------|
| `extract-sql` | All SQL body scripts from views, procedures, functions |
| `find <term>` | Case-insensitive search across all named objects and columns |

## Recommended workflows

### Full documentation
1. `overview` — understand the package and database
2. `list-schemas` — see the schema organization
3. `list-tables` — enumerate all tables
4. `table-detail <name>` — drill into each table for columns, constraints
5. `list-views` → `view-detail` — document views
6. `list-procedures` → `procedure-detail` — document stored procedures
7. `extract-sql` — capture all SQL logic

### Quick audit
1. `summary` — get counts of all object types
2. `list-constraints` — review all constraint definitions
3. `list-indexes` — review indexing strategy
4. `find <term>` — locate specific objects or columns

### Schema exploration
1. `overview` — start with metadata and counts
2. `find <term>` — search for objects by name
3. `table-detail <name>` — get full detail on discovered objects

## Name matching

Detail commands (`table-detail`, `view-detail`, `procedure-detail`, `function-detail`) accept flexible name matching:
- **Exact**: `[Sales].[Customers]`
- **Object name only**: `Customers`
- **Partial match**: `Cust` (resolves if unambiguous)

If a partial match is ambiguous, the tool lists all matches so you can refine.

## Output format

All output is plain text formatted for terminal display. Tables use fixed-width columns for alignment. SQL body scripts are indented under headers.
