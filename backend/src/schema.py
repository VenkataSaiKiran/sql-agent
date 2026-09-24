"""
Introspects the SQLite database to return structured table/column schema info,
used both for UI sidebar display and groundings in LLM system prompts.
"""
import os
import sqlite3
from typing import Any


def get_schema(db_path: str) -> dict[str, Any]:
    """
    Queries SQLite metadata tables to introspect all tables and their column types.
    Uses URI mode=ro to prevent read-only filesystem write errors on Vercel.
    """
    abs_path = os.path.abspath(db_path)
    db_uri = f"file:{abs_path}?mode=ro"

    conn = sqlite3.connect(db_uri, uri=True)
    cur = conn.cursor()

    # Query internal master table for custom user tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    schema = {"database": db_path, "tables": []}
    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}")')
        columns = [{"name": row[1], "type": row[2]} for row in cur.fetchall()]
        schema["tables"].append({"name": table, "columns": columns})

    conn.close()
    return schema


def schema_as_prompt_text(schema: dict[str, Any]) -> str:
    """
    Renders structured schema dictionary into a compact text string suitable
    for inclusion in LLM prompt templates.
    """
    lines = []
    for table in schema["tables"]:
        cols = ", ".join(f"{c['name']} ({c['type']})" for c in table["columns"])
        lines.append(f'- "{table["name"]}": {cols}')
    return "\n".join(lines)


if __name__ == "__main__":
    s = get_schema("demo.db")
    import json

    print(json.dumps(s, indent=2))
    print("\n--- prompt text ---")
    print(schema_as_prompt_text(s))