"""Idempotent Wagtail project ensure (PostgreSQL default)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from xgic.cli.utils.output import print_info, print_success, print_warning
from xgic.cli.wagtail.config import (
    ALLOWED_DB_ADAPTERS,
    DEFAULT_CONFIG_FILE,
    DEFAULT_DB_ADAPTER,
    DEFAULT_SCHEMA_FILE,
    get_db_adapter,
    get_project_name,
    load_create_wagtail_config,
)
from xgic.cli.wagtail.env_helpers import ensure_devcontainer_env
from xgic.cli.wagtail.schema import write_schema

POSTGRES_DATABASES_BLOCK = """DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "wagtail"),
        "USER": os.environ.get("POSTGRES_USER", "wagtail"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,
    }
}"""

_DATABASES_RE = re.compile(
    r"DATABASES\s*=\s*\{(?:[^{}]|\{[^{}]*\})*\}",
    re.DOTALL,
)


def is_wagtail_project_complete(root: Path | None = None) -> bool:
    """Return True when ``manage.py`` and a Django settings package exist."""
    base = Path.cwd() if root is None else root
    if not (base / "manage.py").is_file():
        return False
    return find_settings_base(base) is not None


def find_settings_base(root: Path | None = None) -> Path | None:
    """Locate ``settings/base.py`` under the workspace (skip virtualenvs)."""
    base = Path.cwd() if root is None else root
    skip = {".venv", "venv", "node_modules", ".git"}
    for path in base.rglob("settings/base.py"):
        if skip.intersection(path.relative_to(base).parts):
            continue
        return path
    return None


def ensure_import_os(text: str) -> str:
    """Ensure ``import os`` is present in a Django settings module."""
    if re.search(r"(?m)^import os\s*$", text):
        return text
    if re.search(r"(?m)^from pathlib import Path\s*$", text):
        return re.sub(
            r"(?m)^(from pathlib import Path\s*)$",
            r"\1\nimport os",
            text,
            count=1,
        )
    return "import os\n" + text


def patch_databases(text: str) -> tuple[str, bool]:
    """Replace SQLite DATABASES with env-driven PostgreSQL. Return (text, changed)."""
    if 'django.db.backends.postgresql' in text and "os.environ.get(\"POSTGRES_DB\"" in text:
        return text, False
    match = _DATABASES_RE.search(text)
    if match is None:
        return text, False
    updated = text[: match.start()] + POSTGRES_DATABASES_BLOCK + text[match.end() :]
    updated = ensure_import_os(updated)
    return updated, updated != text


def patch_settings_base(settings_base: Path) -> bool:
    """Patch ``settings/base.py`` in place. Return True if the file changed."""
    original = settings_base.read_text(encoding="utf-8")
    updated, changed = patch_databases(original)
    if not changed:
        return False
    settings_base.write_text(updated, encoding="utf-8")
    return True


def remove_generated_docker_files(root: Path) -> list[str]:
    """Remove Wagtail start Dockerfile artifacts (template consumes GHCR)."""
    removed: list[str] = []
    for name in ("Dockerfile", ".dockerignore"):
        path = root / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    return removed


def default_config_document(project_name: str) -> dict[str, Any]:
    """Return a new create-wagtail-config.json document."""
    return {
        "$schema": "./create-wagtail-config.schema.json",
        "projectName": project_name,
        "composeProjectName": "xgic-wagtail",
        "dbAdapter": DEFAULT_DB_ADAPTER,
        "dbName": "wagtail",
        "dbUser": "wagtail",
    }


def ensure_config_file(
    path: Path = DEFAULT_CONFIG_FILE,
    *,
    project_name: str | None = None,
) -> bool:
    """Write create-wagtail-config.json when missing. Return True if written."""
    if path.is_file():
        return False
    name = project_name or get_project_name()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(default_config_document(name), indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def run_wagtail_start(project_name: str, dest: Path) -> int:
    """Run ``wagtail start <name> .`` in *dest*. Return process exit code."""
    exe = shutil.which("wagtail")
    if exe is None:
        print_warning(
            "wagtail is not on PATH. Reopen in the Dev Container image "
            "(ghcr.io/xgic/wagtail-dev) or install Wagtail 8.0."
        )
        return 1
    result = subprocess.run(
        [exe, "start", project_name, "."],
        cwd=str(dest),
        check=False,
    )
    return int(result.returncode)


def ensure_wagtail_project(
    *,
    quiet: bool = False,
    root: Path | None = None,
) -> int:
    """Idempotent first-run: config, env, wagtail start, PostgreSQL settings."""
    base = Path.cwd() if root is None else root
    orig = Path.cwd()
    os.chdir(base)
    try:
        return _ensure_wagtail_project(quiet=quiet, root=base)
    finally:
        os.chdir(orig)


def _ensure_wagtail_project(*, quiet: bool, root: Path) -> int:
    cfg = load_create_wagtail_config(root / DEFAULT_CONFIG_FILE)
    adapter = get_db_adapter(cfg)
    if adapter not in ALLOWED_DB_ADAPTERS:
        print_warning(
            f"dbAdapter {adapter!r} is not supported. "
            "XGIC default is PostgreSQL (set dbAdapter to 'postgres')."
        )
        return 1

    project_name = get_project_name(cfg)
    wrote_schema = False
    schema_path = root / DEFAULT_SCHEMA_FILE
    if not schema_path.is_file():
        write_schema(schema_path)
        wrote_schema = True
    wrote_config = ensure_config_file(
        root / DEFAULT_CONFIG_FILE,
        project_name=project_name,
    )
    wrote_env = ensure_devcontainer_env(
        config_path=root / DEFAULT_CONFIG_FILE,
        env_file=root / ".devcontainer" / ".env",
    )
    if not quiet:
        if wrote_schema:
            print_info(f"Wrote {DEFAULT_SCHEMA_FILE}")
        if wrote_config:
            print_info(f"Wrote {DEFAULT_CONFIG_FILE}")
        if wrote_env:
            print_info("Wrote .devcontainer/.env (Compose Postgres credentials)")

    if is_wagtail_project_complete(root):
        settings_base = find_settings_base(root)
        changed = patch_settings_base(settings_base) if settings_base else False
        if not quiet:
            if changed:
                print_success("Django DATABASES now use Compose PostgreSQL.")
            else:
                print_success("Wagtail project already present (PostgreSQL settings).")
        return 0

    if not quiet:
        print_info(f"Running: wagtail start {project_name} .")
    rc = run_wagtail_start(project_name, root)
    if rc != 0:
        return rc

    removed = remove_generated_docker_files(root)
    if removed and not quiet:
        print_info(
            "Removed generated "
            + ", ".join(removed)
            + " (template consumes ghcr.io/xgic/wagtail-dev)."
        )

    settings_base = find_settings_base(root)
    if settings_base is None:
        print_warning("wagtail start finished but settings/base.py was not found.")
        return 1
    patch_settings_base(settings_base)
    if not quiet:
        print_success(
            "Wagtail site scaffolded with PostgreSQL "
            "(POSTGRES_HOST=postgres). Next: python manage.py migrate"
        )
    return 0
