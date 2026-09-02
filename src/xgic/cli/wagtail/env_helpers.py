"""Compose ``.devcontainer/.env`` helpers for Wagtail + PostgreSQL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from xgic.cli.wagtail.config import (
    DEFAULT_CONFIG_FILE,
    get_db_config,
    load_create_wagtail_config,
)

ENV_FILE = Path(".devcontainer/.env")


def parse_dotenv(content: str) -> dict[str, str]:
    """Parse KEY=value assignments from .env text (last key wins)."""
    values: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def generate_env_content(
    *,
    config: dict[str, Any] | None = None,
    preserve: dict[str, str] | None = None,
) -> str:
    """Return compose .env content for PostgreSQL.

    First-run uses a stable local password when none is preserved so an
    already-started Compose Postgres with the template default still matches.
    """
    cfg = config if config is not None else load_create_wagtail_config()
    db_name, db_user = get_db_config(cfg)
    kept = preserve or {}
    password = kept.get("POSTGRES_PASSWORD") or "wagtail"
    return (
        f"POSTGRES_USER={db_user}\n"
        f"POSTGRES_PASSWORD={password}\n"
        f"POSTGRES_DB={db_name}\n"
        f"PGUSER={db_user}\n"
        f"PGDATABASE={db_name}\n"
        f"POSTGRES_HOST=postgres\n"
        f"POSTGRES_PORT=5432\n"
        f"DATABASE_URL=postgres://{db_user}:{password}@postgres:5432/{db_name}\n"
    )


def ensure_devcontainer_env(
    *,
    config_path: Path = DEFAULT_CONFIG_FILE,
    env_file: Path = ENV_FILE,
) -> bool:
    """Create ``.devcontainer/.env`` when missing. Return True if written."""
    if env_file.is_file():
        return False
    cfg = load_create_wagtail_config(config_path)
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(generate_env_content(config=cfg), encoding="utf-8")
    return True
