"""Wagtail product defaults and create-wagtail-config.json readers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_FILE = Path(".devcontainer/create-wagtail-config.json")
DEFAULT_SCHEMA_FILE = Path(".devcontainer/create-wagtail-config.schema.json")
DEFAULT_COMPOSE_FILE = Path(".devcontainer/docker-compose.yml")
DEFAULT_PROJECT_NAME = "mysite"
DEFAULT_COMPOSE_PROJECT = "xgic-wagtail"
DEFAULT_DB_ADAPTER = "postgres"
DEFAULT_DB_NAME = "wagtail"
DEFAULT_DB_USER = "wagtail"
ALLOWED_DB_ADAPTERS = frozenset({DEFAULT_DB_ADAPTER})


def _is_compose_safe_name(name: str) -> bool:
    if not name or not name[0].isalnum():
        return False
    return all(c.isalnum() or c in "_-" for c in name) and len(name) <= 63


def load_create_wagtail_config(
    config_path: Path = DEFAULT_CONFIG_FILE,
) -> dict[str, Any]:
    """Load create-wagtail-config.json or return XGIC defaults."""
    defaults: dict[str, Any] = {
        "projectName": DEFAULT_PROJECT_NAME,
        "composeProjectName": DEFAULT_COMPOSE_PROJECT,
        "dbAdapter": DEFAULT_DB_ADAPTER,
        "dbName": DEFAULT_DB_NAME,
        "dbUser": DEFAULT_DB_USER,
    }
    if not config_path.is_file():
        return defaults
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    for key, value in data.items():
        if key == "$schema":
            continue
        if value is not None:
            defaults[key] = value
    return defaults


def get_project_name(config: dict[str, Any] | None = None) -> str:
    """Return Django/Wagtail project package name."""
    cfg = config if config is not None else load_create_wagtail_config()
    name = cfg.get("projectName")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return DEFAULT_PROJECT_NAME


def get_db_adapter(config: dict[str, Any] | None = None) -> str:
    """Return database adapter (XGIC default: postgres)."""
    cfg = config if config is not None else load_create_wagtail_config()
    adapter = str(cfg.get("dbAdapter") or DEFAULT_DB_ADAPTER).strip().lower()
    if adapter in {"postgresql", "psql"}:
        return DEFAULT_DB_ADAPTER
    return adapter or DEFAULT_DB_ADAPTER


def get_db_config(config: dict[str, Any] | None = None) -> tuple[str, str]:
    """Return ``(dbName, dbUser)``."""
    cfg = config if config is not None else load_create_wagtail_config()
    db_name = str(cfg.get("dbName") or DEFAULT_DB_NAME).strip() or DEFAULT_DB_NAME
    db_user = str(cfg.get("dbUser") or DEFAULT_DB_USER).strip() or DEFAULT_DB_USER
    return db_name, db_user


def get_compose_project_name(config: dict[str, Any] | None = None) -> str:
    """Return Docker Compose project name.

    Precedence: ``XGIC_COMPOSE_PROJECT``, config ``composeProjectName``,
    Compose file ``name:``, then ``DEFAULT_COMPOSE_PROJECT``.
    """
    env_name = os.environ.get("XGIC_COMPOSE_PROJECT", "").strip().lower()
    if env_name and _is_compose_safe_name(env_name):
        return env_name
    cfg = config if config is not None else load_create_wagtail_config()
    named = str(cfg.get("composeProjectName") or "").strip().lower()
    if named and _is_compose_safe_name(named):
        return named
    compose_name = _compose_name_from_file(DEFAULT_COMPOSE_FILE)
    if compose_name:
        return compose_name
    return DEFAULT_COMPOSE_PROJECT


def _compose_name_from_file(compose_path: Path) -> str | None:
    if not compose_path.is_file():
        return None
    try:
        for line in compose_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped.startswith("name:"):
                continue
            raw = stripped.split(":", 1)[1].strip().strip("\"'")
            if raw and _is_compose_safe_name(raw.lower()):
                return raw.lower()
    except OSError:
        return None
    return None
