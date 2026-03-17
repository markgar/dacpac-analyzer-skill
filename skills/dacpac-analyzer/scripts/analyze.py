#!/usr/bin/env python3
"""DACPAC/BACPAC schema analyzer CLI.

Usage:
    python analyze.py <path-to-dacpac> <command> [args...]

Commands:
    overview                  Package metadata, origin info, object counts
    summary                   High-level stats (counts per object type)
    list-schemas              All schemas
    list-tables               All tables with column counts
    table-detail <name>       Full table detail — columns, types, nullability
    list-views                All views with column counts
    view-detail <name>        View with columns and query script
    list-procedures           All stored procedures
    procedure-detail <name>   Procedure with parameters and body
    list-functions            All functions (scalar + inline TVF)
    function-detail <name>    Function with parameters, return type, body
    list-constraints          PKs, FKs, unique, check, default constraints
    list-indexes              All indexes
    list-sequences            All sequences
    list-table-types          All user-defined table types
    list-roles                All database roles
    list-permissions          All permission statements
    extract-sql               All SQL body scripts from views, procs, functions
    find <term>               Case-insensitive search across all named objects
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as: python scripts/analyze.py ...
# by making the scripts dir importable
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from orchestration.factory import create_package_reader
from models.package import Package
from models.parsed_name import ParsedName


# ── Helpers ──────────────────────────────────────────────────────────


def _display_name(pn: ParsedName) -> str:
    """Format a ParsedName for display: [schema].[object] or just [object]."""
    if pn.schema_name and pn.object_name:
        return f"[{pn.schema_name}].[{pn.object_name}]"
    if pn.object_name:
        return f"[{pn.object_name}]"
    return pn.parts[-1] if pn.parts else pn.raw


def _type_display(ts) -> str:
    """Format a TypeSpecifier for display."""
    if ts is None:
        return "?"
    name = ts.type_name
    if ts.is_max:
        return f"{name}(MAX)"
    if ts.length is not None:
        return f"{name}({ts.length})"
    if ts.precision is not None and ts.scale is not None:
        return f"{name}({ts.precision},{ts.scale})"
    if ts.precision is not None:
        return f"{name}({ts.precision})"
    return name


def _match(term: str, *texts: str | None) -> bool:
    """Case-insensitive substring match against multiple candidates."""
    t = term.lower()
    return any(t in (s or "").lower() for s in texts)


def _print_line():
    print("-" * 72)


# ── Commands ─────────────────────────────────────────────────────────


def cmd_overview(pkg: Package):
    """Package metadata, origin info, and object counts."""
    print("PACKAGE OVERVIEW")
    _print_line()
    print(f"  Name:             {pkg.metadata.name}")
    print(f"  Version:          {pkg.metadata.version}")
    print(f"  Format version:   {pkg.format_version}")
    print(f"  Schema version:   {pkg.schema_version}")
    print(f"  DSP name:         {pkg.dsp_name}")
    print()

    o = pkg.origin
    if o.server_version:
        print(f"  Server version:   {o.server_version}")
    if o.product_version:
        print(f"  Product version:  {o.product_version}")
    if o.export_timestamp:
        print(f"  Exported:         {o.export_timestamp}")
    if o.source_database_size_kb is not None:
        print(f"  DB size:          {o.source_database_size_kb:,} KB")
    if o.total_row_count is not None:
        print(f"  Total rows:       {o.total_row_count:,}")
    if o.contains_exported_data:
        print("  Contains data:    Yes (BACPAC)")
    print()

    counts = o.object_counts
    if counts:
        print("  Object counts (from Origin.xml):")
        for obj_type, count in sorted(counts.items()):
            print(f"    {obj_type:30s}  {count:>6,}")
    print()

    cmd_summary(pkg)


def cmd_summary(pkg: Package):
    """High-level stats — counts per object type."""
    db = pkg.database_model
    items = [
        ("Schemas", len(db.schemas)),
        ("Tables", len(db.tables)),
        ("Views", len(db.views)),
        ("Stored procedures", len(db.procedures)),
        ("Scalar functions", len(db.scalar_functions)),
        ("Inline TVFs", len(db.inline_tvfs)),
        ("Sequences", len(db.sequences)),
        ("Table types", len(db.table_types)),
        ("Primary keys", len(db.primary_keys)),
        ("Foreign keys", len(db.foreign_keys)),
        ("Unique constraints", len(db.unique_constraints)),
        ("Check constraints", len(db.check_constraints)),
        ("Default constraints", len(db.default_constraints)),
        ("Indexes", len(db.indexes)),
        ("Roles", len(db.roles)),
        ("Permissions", len(db.permissions)),
        ("Filegroups", len(db.filegroups)),
        ("Partition functions", len(db.partition_functions)),
        ("Partition schemes", len(db.partition_schemes)),
        ("Extended properties", len(db.extended_properties)),
    ]
    print("SCHEMA SUMMARY")
    _print_line()
    for label, count in items:
        if count > 0:
            print(f"  {label:30s}  {count:>6,}")
    total = sum(c for _, c in items)
    _print_line()
    print(f"  {'Total':30s}  {total:>6,}")


def cmd_list_schemas(pkg: Package):
    """List all schemas."""
    schemas = pkg.database_model.schemas
    if not schemas:
        print("No schemas found.")
        return
    print(f"SCHEMAS ({len(schemas)})")
    _print_line()
    for s in sorted(schemas, key=lambda x: _display_name(x.name)):
        auth = _display_name(s.authorizer)
        print(f"  {_display_name(s.name):40s}  authorizer: {auth}")


def cmd_list_tables(pkg: Package):
    """List all tables with column counts."""
    tables = pkg.database_model.tables
    if not tables:
        print("No tables found.")
        return
    print(f"TABLES ({len(tables)})")
    _print_line()
    print(f"  {'Name':50s}  {'Cols':>5s}  {'Notes'}")
    _print_line()
    for t in sorted(tables, key=lambda x: _display_name(x.name)):
        notes = []
        if t.is_memory_optimized:
            notes.append("memory-optimized")
        if t.temporal_history_table:
            notes.append("temporal")
        if t.compression_options:
            notes.append("compressed")
        print(f"  {_display_name(t.name):50s}  {len(t.columns):>5d}  {', '.join(notes)}")


def cmd_table_detail(pkg: Package, name: str):
    """Full detail for a single table."""
    table = _find_object(pkg.database_model.tables, name)
    if table is None:
        print(f"Table not found: {name}")
        print("Hint: use 'list-tables' to see all tables, or 'find' to search.")
        return

    print(f"TABLE: {_display_name(table.name)}")
    print(f"  Schema: {_display_name(table.schema_ref)}")
    if table.filegroup:
        print(f"  Filegroup: {_display_name(table.filegroup)}")
    if table.is_memory_optimized:
        print(f"  Memory optimized: Yes")
        if table.durability:
            print(f"  Durability: {table.durability.value}")
    if table.temporal_history_table:
        print(f"  Temporal history: {_display_name(table.temporal_history_table)}")
    print()

    if table.columns:
        print(f"  COLUMNS ({len(table.columns)}):")
        print(f"    {'#':>3s}  {'Name':30s}  {'Type':20s}  {'Null':>4s}  {'Notes'}")
        _print_line()
        for c in table.columns:
            col_name = c.name.parts[-1] if c.name.parts else c.name.raw
            nullable = "YES" if c.is_nullable else "NO"
            notes = []
            if c.is_computed:
                notes.append(f"computed: {c.expression_script or '?'}")
            if c.is_persisted:
                notes.append("persisted")
            if c.generated_always_type:
                notes.append(f"generated: {c.generated_always_type}")
            print(f"    {c.ordinal:>3d}  {col_name:30s}  {_type_display(c.type_specifier):20s}  {nullable:>4s}  {', '.join(notes)}")
    print()

    # Show related constraints
    _show_table_constraints(pkg, table.name)


def _show_table_constraints(pkg: Package, table_name: ParsedName):
    """Show constraints related to a table."""
    db = pkg.database_model
    raw = table_name.raw

    pks = [pk for pk in db.primary_keys if pk.defining_table.raw == raw]
    if pks:
        for pk in pks:
            cols = ", ".join(
                f"{c.column_ref.parts[-1]} {c.sort_order.value}" for c in pk.columns
            )
            print(f"  PRIMARY KEY: {_display_name(pk.name)}")
            print(f"    Columns: {cols}")

    fks = [fk for fk in db.foreign_keys if fk.defining_table.raw == raw]
    if fks:
        print()
        print(f"  FOREIGN KEYS ({len(fks)}):")
        for fk in fks:
            local = ", ".join(p.parts[-1] for p in fk.columns)
            remote = ", ".join(p.parts[-1] for p in fk.foreign_columns)
            print(f"    {_display_name(fk.name)}")
            print(f"      ({local}) → {_display_name(fk.foreign_table)} ({remote})")

    uqs = [u for u in db.unique_constraints if u.defining_table.raw == raw]
    if uqs:
        print()
        print(f"  UNIQUE CONSTRAINTS ({len(uqs)}):")
        for u in uqs:
            cols = ", ".join(c.column_ref.parts[-1] for c in u.columns)
            print(f"    {_display_name(u.name)}: ({cols})")

    cks = [c for c in db.check_constraints if c.defining_table.raw == raw]
    if cks:
        print()
        print(f"  CHECK CONSTRAINTS ({len(cks)}):")
        for ck in cks:
            print(f"    {_display_name(ck.name)}: {ck.expression}")

    dfs = [d for d in db.default_constraints if d.defining_table.raw == raw]
    if dfs:
        print()
        print(f"  DEFAULTS ({len(dfs)}):")
        for df in dfs:
            col = df.for_column.parts[-1] if df.for_column.parts else df.for_column.raw
            print(f"    {_display_name(df.name)}: {col} = {df.expression}")

    idxs = [i for i in db.indexes if i.indexed_object.raw == raw]
    if idxs:
        print()
        print(f"  INDEXES ({len(idxs)}):")
        for ix in idxs:
            cols = ", ".join(
                f"{c.column_ref.parts[-1]} {c.sort_order.value}" for c in ix.columns
            )
            ix_type = "COLUMNSTORE" if ix.is_columnstore else "NONCLUSTERED"
            print(f"    {_display_name(ix.name)} ({ix_type}): ({cols})")


def cmd_list_views(pkg: Package):
    """List all views."""
    views = pkg.database_model.views
    if not views:
        print("No views found.")
        return
    print(f"VIEWS ({len(views)})")
    _print_line()
    print(f"  {'Name':50s}  {'Cols':>5s}")
    _print_line()
    for v in sorted(views, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(v.name):50s}  {len(v.columns):>5d}")


def cmd_view_detail(pkg: Package, name: str):
    """Full detail for a single view."""
    view = _find_object(pkg.database_model.views, name)
    if view is None:
        print(f"View not found: {name}")
        return

    print(f"VIEW: {_display_name(view.name)}")
    print(f"  Schema: {_display_name(view.schema_ref)}")
    print()

    if view.columns:
        print(f"  COLUMNS ({len(view.columns)}):")
        print(f"    {'#':>3s}  {'Name':30s}  {'Type':20s}  {'Null':>4s}")
        _print_line()
        for c in view.columns:
            col_name = c.name.parts[-1] if c.name.parts else c.name.raw
            nullable = "YES" if c.is_nullable else "NO"
            print(f"    {c.ordinal:>3d}  {col_name:30s}  {_type_display(c.type_specifier):20s}  {nullable:>4s}")
    print()

    if view.query_script:
        print("  QUERY:")
        _print_line()
        for line in view.query_script.splitlines():
            print(f"    {line}")


def cmd_list_procedures(pkg: Package):
    """List all stored procedures."""
    procs = pkg.database_model.procedures
    if not procs:
        print("No stored procedures found.")
        return
    print(f"STORED PROCEDURES ({len(procs)})")
    _print_line()
    print(f"  {'Name':50s}  {'Params':>6s}")
    _print_line()
    for p in sorted(procs, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(p.name):50s}  {len(p.parameters):>6d}")


def cmd_procedure_detail(pkg: Package, name: str):
    """Full detail for a stored procedure."""
    proc = _find_object(pkg.database_model.procedures, name)
    if proc is None:
        print(f"Procedure not found: {name}")
        return

    print(f"PROCEDURE: {_display_name(proc.name)}")
    print(f"  Schema: {_display_name(proc.schema_ref)}")
    if proc.execute_as:
        print(f"  Execute as: {proc.execute_as}")
    print(f"  ANSI nulls: {proc.is_ansi_nulls_on}")
    print(f"  Quoted identifiers: {proc.is_quoted_identifiers_on}")
    print()

    if proc.parameters:
        print(f"  PARAMETERS ({len(proc.parameters)}):")
        for p in proc.parameters:
            p_name = p.name.parts[-1] if p.name.parts else p.name.raw
            direction = "OUTPUT" if p.is_output else "INPUT"
            print(f"    {p_name:30s}  {_type_display(p.type_specifier):20s}  {direction}")
        print()

    if proc.body_script:
        print("  BODY:")
        _print_line()
        for line in proc.body_script.splitlines():
            print(f"    {line}")

    if proc.body_dependencies:
        print()
        print(f"  DEPENDENCIES ({len(proc.body_dependencies)}):")
        for dep in proc.body_dependencies:
            print(f"    {_display_name(dep)}")


def cmd_list_functions(pkg: Package):
    """List all functions (scalar + inline TVF)."""
    scalars = pkg.database_model.scalar_functions
    tvfs = pkg.database_model.inline_tvfs
    total = len(scalars) + len(tvfs)
    if total == 0:
        print("No functions found.")
        return

    print(f"FUNCTIONS ({total})")
    _print_line()
    print(f"  {'Name':50s}  {'Type':12s}  {'Params':>6s}")
    _print_line()
    for f in sorted(scalars, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(f.name):50s}  {'Scalar':12s}  {len(f.parameters):>6d}")
    for f in sorted(tvfs, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(f.name):50s}  {'Inline TVF':12s}  {len(f.parameters):>6d}")


def cmd_function_detail(pkg: Package, name: str):
    """Full detail for a function."""
    func = _find_object(pkg.database_model.scalar_functions, name)
    kind = "SCALAR FUNCTION"
    if func is None:
        func = _find_object(pkg.database_model.inline_tvfs, name)
        kind = "INLINE TABLE-VALUED FUNCTION"
    if func is None:
        print(f"Function not found: {name}")
        return

    print(f"{kind}: {_display_name(func.name)}")
    print(f"  Schema: {_display_name(func.schema_ref)}")

    if hasattr(func, "return_type"):
        print(f"  Return type: {_type_display(func.return_type)}")
    print()

    if func.parameters:
        print(f"  PARAMETERS ({len(func.parameters)}):")
        for p in func.parameters:
            p_name = p.name.parts[-1] if p.name.parts else p.name.raw
            direction = "OUTPUT" if p.is_output else "INPUT"
            print(f"    {p_name:30s}  {_type_display(p.type_specifier):20s}  {direction}")
        print()

    if hasattr(func, "columns") and func.columns:
        print(f"  COLUMNS ({len(func.columns)}):")
        for c in func.columns:
            col_name = c.name.parts[-1] if c.name.parts else c.name.raw
            print(f"    {col_name:30s}  {_type_display(c.type_specifier)}")
        print()

    if func.body_script:
        print("  BODY:")
        _print_line()
        for line in func.body_script.splitlines():
            print(f"    {line}")

    if func.body_dependencies:
        print()
        print(f"  DEPENDENCIES ({len(func.body_dependencies)}):")
        for dep in func.body_dependencies:
            print(f"    {_display_name(dep)}")


def cmd_list_constraints(pkg: Package):
    """List all constraints (PK, FK, unique, check, default)."""
    db = pkg.database_model
    sections = [
        ("PRIMARY KEYS", db.primary_keys),
        ("FOREIGN KEYS", db.foreign_keys),
        ("UNIQUE CONSTRAINTS", db.unique_constraints),
        ("CHECK CONSTRAINTS", db.check_constraints),
        ("DEFAULT CONSTRAINTS", db.default_constraints),
    ]
    total = sum(len(items) for _, items in sections)
    if total == 0:
        print("No constraints found.")
        return

    print(f"CONSTRAINTS ({total})")
    _print_line()

    for label, items in sections:
        if not items:
            continue
        print(f"\n  {label} ({len(items)}):")
        for item in sorted(items, key=lambda x: _display_name(x.name) if x.name else ""):
            dn = _display_name(item.name) if item.name else "(unnamed)"
            table = _display_name(item.defining_table)

            if hasattr(item, "columns") and item.columns:
                if hasattr(item.columns[0], "column_ref"):
                    cols = ", ".join(c.column_ref.parts[-1] for c in item.columns)
                else:
                    cols = ", ".join(c.parts[-1] for c in item.columns)
            else:
                cols = ""

            if hasattr(item, "foreign_table"):
                remote = ", ".join(p.parts[-1] for p in item.foreign_columns)
                print(f"    {dn:40s}  {table} ({cols}) → {_display_name(item.foreign_table)} ({remote})")
            elif hasattr(item, "expression"):
                if hasattr(item, "for_column"):
                    col = item.for_column.parts[-1] if item.for_column.parts else ""
                    print(f"    {dn:40s}  {table}.{col} = {item.expression}")
                else:
                    print(f"    {dn:40s}  {table}: {item.expression}")
            elif cols:
                print(f"    {dn:40s}  {table} ({cols})")
            else:
                print(f"    {dn:40s}  {table}")


def cmd_list_indexes(pkg: Package):
    """List all indexes."""
    indexes = pkg.database_model.indexes
    if not indexes:
        print("No indexes found.")
        return
    print(f"INDEXES ({len(indexes)})")
    _print_line()
    print(f"  {'Name':40s}  {'Object':30s}  {'Type':12s}  {'Columns'}")
    _print_line()
    for ix in sorted(indexes, key=lambda x: _display_name(x.name)):
        ix_type = "COLUMNSTORE" if ix.is_columnstore else "NONCLUSTERED"
        cols = ", ".join(
            f"{c.column_ref.parts[-1]} {c.sort_order.value}" for c in ix.columns
        )
        print(f"  {_display_name(ix.name):40s}  {_display_name(ix.indexed_object):30s}  {ix_type:12s}  {cols}")


def cmd_list_sequences(pkg: Package):
    """List all sequences."""
    seqs = pkg.database_model.sequences
    if not seqs:
        print("No sequences found.")
        return
    print(f"SEQUENCES ({len(seqs)})")
    _print_line()
    for s in sorted(seqs, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(s.name):40s}  {_type_display(s.type_specifier):15s}  start={s.start_value}  inc={s.increment}")


def cmd_list_table_types(pkg: Package):
    """List all user-defined table types."""
    tts = pkg.database_model.table_types
    if not tts:
        print("No table types found.")
        return
    print(f"TABLE TYPES ({len(tts)})")
    _print_line()
    for tt in sorted(tts, key=lambda x: _display_name(x.name)):
        pk = f"  PK: {_display_name(tt.primary_key.name)}" if tt.primary_key else ""
        print(f"  {_display_name(tt.name):40s}  {len(tt.columns)} columns{pk}")


def cmd_list_roles(pkg: Package):
    """List all database roles."""
    roles = pkg.database_model.roles
    if not roles:
        print("No roles found.")
        return
    print(f"ROLES ({len(roles)})")
    _print_line()
    for r in sorted(roles, key=lambda x: _display_name(x.name)):
        print(f"  {_display_name(r.name):40s}  authorizer: {_display_name(r.authorizer)}")


def cmd_list_permissions(pkg: Package):
    """List all permission statements."""
    perms = pkg.database_model.permissions
    if not perms:
        print("No permissions found.")
        return
    print(f"PERMISSIONS ({len(perms)})")
    _print_line()
    for p in sorted(perms, key=lambda x: x.permission_code):
        grantee = _display_name(p.grantee)
        obj = _display_name(p.secured_object) if p.secured_object else "(database)"
        print(f"  {p.permission_code:20s}  TO {grantee:30s}  ON {obj}")


def cmd_extract_sql(pkg: Package):
    """Extract all SQL body scripts from views, procedures, and functions."""
    db = pkg.database_model
    found = False

    for proc in sorted(db.procedures, key=lambda x: _display_name(x.name)):
        if proc.body_script:
            found = True
            print(f"-- PROCEDURE: {_display_name(proc.name)}")
            _print_line()
            print(proc.body_script)
            print()

    for view in sorted(db.views, key=lambda x: _display_name(x.name)):
        if view.query_script:
            found = True
            print(f"-- VIEW: {_display_name(view.name)}")
            _print_line()
            print(view.query_script)
            print()

    for fn in sorted(db.scalar_functions, key=lambda x: _display_name(x.name)):
        if fn.body_script:
            found = True
            print(f"-- SCALAR FUNCTION: {_display_name(fn.name)}")
            _print_line()
            print(fn.body_script)
            print()

    for fn in sorted(db.inline_tvfs, key=lambda x: _display_name(x.name)):
        if fn.body_script:
            found = True
            print(f"-- INLINE TVF: {_display_name(fn.name)}")
            _print_line()
            print(fn.body_script)
            print()

    if not found:
        print("No SQL body scripts found.")


def cmd_find(pkg: Package, term: str):
    """Case-insensitive search across all named objects."""
    db = pkg.database_model
    results: list[tuple[str, str]] = []

    for s in db.schemas:
        if _match(term, _display_name(s.name)):
            results.append(("Schema", _display_name(s.name)))

    for t in db.tables:
        if _match(term, _display_name(t.name)):
            results.append(("Table", _display_name(t.name)))
        for c in t.columns:
            col_name = c.name.parts[-1] if c.name.parts else c.name.raw
            if _match(term, col_name):
                results.append(("Column", f"{_display_name(t.name)}.{col_name}"))

    for v in db.views:
        if _match(term, _display_name(v.name)):
            results.append(("View", _display_name(v.name)))

    for p in db.procedures:
        if _match(term, _display_name(p.name)):
            results.append(("Procedure", _display_name(p.name)))

    for f in db.scalar_functions:
        if _match(term, _display_name(f.name)):
            results.append(("Scalar Function", _display_name(f.name)))

    for f in db.inline_tvfs:
        if _match(term, _display_name(f.name)):
            results.append(("Inline TVF", _display_name(f.name)))

    for seq in db.sequences:
        if _match(term, _display_name(seq.name)):
            results.append(("Sequence", _display_name(seq.name)))

    for tt in db.table_types:
        if _match(term, _display_name(tt.name)):
            results.append(("Table Type", _display_name(tt.name)))

    for ix in db.indexes:
        if _match(term, _display_name(ix.name)):
            results.append(("Index", _display_name(ix.name)))

    for pk in db.primary_keys:
        if _match(term, _display_name(pk.name)):
            results.append(("Primary Key", _display_name(pk.name)))

    for fk in db.foreign_keys:
        if _match(term, _display_name(fk.name)):
            results.append(("Foreign Key", _display_name(fk.name)))

    if not results:
        print(f"No matches for: {term}")
        return

    print(f"SEARCH RESULTS for '{term}' ({len(results)} matches)")
    _print_line()
    for kind, name in results:
        print(f"  {kind:20s}  {name}")


# ── Object finder ────────────────────────────────────────────────────


def _find_object(collection, name: str):
    """Find an object by name (case-insensitive, partial match)."""
    term = name.lower()

    # Exact match on display name
    for obj in collection:
        if _display_name(obj.name).lower() == term:
            return obj

    # Exact match on object_name part
    for obj in collection:
        if obj.name.object_name and obj.name.object_name.lower() == term:
            return obj

    # Partial match
    matches = []
    for obj in collection:
        dn = _display_name(obj.name).lower()
        on = (obj.name.object_name or "").lower()
        if term in dn or term in on:
            matches.append(obj)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous name '{name}' — {len(matches)} matches:")
        for m in matches:
            print(f"  {_display_name(m.name)}")
        return None
    return None


# ── Dispatcher ───────────────────────────────────────────────────────


COMMANDS = {
    "overview": (cmd_overview, 0),
    "summary": (cmd_summary, 0),
    "list-schemas": (cmd_list_schemas, 0),
    "list-tables": (cmd_list_tables, 0),
    "table-detail": (cmd_table_detail, 1),
    "list-views": (cmd_list_views, 0),
    "view-detail": (cmd_view_detail, 1),
    "list-procedures": (cmd_list_procedures, 0),
    "procedure-detail": (cmd_procedure_detail, 1),
    "list-functions": (cmd_list_functions, 0),
    "function-detail": (cmd_function_detail, 1),
    "list-constraints": (cmd_list_constraints, 0),
    "list-indexes": (cmd_list_indexes, 0),
    "list-sequences": (cmd_list_sequences, 0),
    "list-table-types": (cmd_list_table_types, 0),
    "list-roles": (cmd_list_roles, 0),
    "list-permissions": (cmd_list_permissions, 0),
    "extract-sql": (cmd_extract_sql, 0),
    "find": (cmd_find, 1),
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    dacpac_path = Path(sys.argv[1])
    command = sys.argv[2].lower()

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(sorted(COMMANDS))}")
        sys.exit(1)

    handler, nargs = COMMANDS[command]

    if nargs > 0 and len(sys.argv) < 4:
        print(f"Command '{command}' requires an argument.")
        sys.exit(1)

    if not dacpac_path.exists():
        print(f"File not found: {dacpac_path}")
        sys.exit(1)

    reader = create_package_reader()
    try:
        pkg = reader.read_package(dacpac_path)
    except Exception as e:
        print(f"Error reading {dacpac_path}: {e}")
        sys.exit(1)

    if nargs == 0:
        handler(pkg)
    elif nargs == 1:
        handler(pkg, sys.argv[3])


if __name__ == "__main__":
    main()
