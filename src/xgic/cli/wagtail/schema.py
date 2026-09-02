"""JSON Schema for ``create-wagtail-config.json`` (editor IntelliSense)."""

from __future__ import annotations

import json
from pathlib import Path

from xgic.cli.wagtail.config import DEFAULT_SCHEMA_FILE

WAGTAIL_CONFIG_SCHEMA: dict[str, object] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "XGIC Wagtail create-wagtail-config",
    "description": (
        "Workspace config for xgic wagtail setup. "
        "XGIC default database is PostgreSQL. SQLite is not supported."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["projectName", "dbAdapter"],
    "properties": {
        "$schema": {"type": "string"},
        "projectName": {
            "type": "string",
            "pattern": "^[A-Za-z][A-Za-z0-9_]*$",
            "description": (
                "Django project package name passed to `wagtail start` "
                "(letters, digits, underscore)."
            ),
            "examples": ["mysite", "website"],
        },
        "composeProjectName": {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9_-]{0,62}$",
            "description": "Docker Compose project name for this workspace.",
            "examples": ["xgic-wagtail"],
        },
        "dbAdapter": {
            "type": "string",
            "enum": ["postgres"],
            "description": "Database adapter. XGIC default and only supported value is postgres.",
        },
        "dbName": {
            "type": "string",
            "minLength": 1,
            "description": "PostgreSQL database name (Compose POSTGRES_DB).",
            "examples": ["wagtail"],
        },
        "dbUser": {
            "type": "string",
            "minLength": 1,
            "description": "PostgreSQL role (Compose POSTGRES_USER / PGUSER).",
            "examples": ["wagtail"],
        },
    },
}


def write_schema(path: Path = DEFAULT_SCHEMA_FILE) -> Path:
    """Write the schema JSON file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(WAGTAIL_CONFIG_SCHEMA, indent=2) + "\n", encoding="utf-8")
    return path
