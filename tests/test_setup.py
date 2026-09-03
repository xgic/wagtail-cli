"""Tests for Wagtail setup (PostgreSQL default, no SQLite)."""

from __future__ import annotations

from pathlib import Path

from xgic.cli.wagtail.config import get_db_adapter, load_create_wagtail_config
from xgic.cli.wagtail.env_helpers import generate_env_content
from xgic.cli.wagtail.project import (
    ensure_postgres_installed_apps,
    ensure_wagtail_project,
    is_wagtail_project_complete,
    patch_databases,
    remove_generated_docker_files,
)

SQLITE_SETTINGS = '''from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT_DIR.parent

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
'''


def test_load_defaults_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_create_wagtail_config(tmp_path / "missing.json")
    assert cfg["dbAdapter"] == "postgres"
    assert cfg["projectName"] == "mysite"


def test_get_db_adapter_postgres() -> None:
    assert get_db_adapter({"dbAdapter": "postgres"}) == "postgres"
    assert get_db_adapter({"dbAdapter": "PostgreSQL"}) == "postgres"


def test_patch_databases_replaces_sqlite() -> None:
    updated, changed = patch_databases(SQLITE_SETTINGS)
    assert changed
    assert "django.db.backends.postgresql" in updated
    assert "sqlite3" not in updated
    assert "import os" in updated
    assert "POSTGRES_HOST" in updated


def test_ensure_postgres_installed_apps() -> None:
    src = 'INSTALLED_APPS = [\n    "django.contrib.admin",\n]\n'
    updated, changed = ensure_postgres_installed_apps(src)
    assert changed
    assert '"django.contrib.postgres"' in updated
    again, changed_again = ensure_postgres_installed_apps(updated)
    assert changed_again is False
    assert again == updated


def test_patch_databases_idempotent() -> None:
    once, _ = patch_databases(SQLITE_SETTINGS)
    twice, changed = patch_databases(once)
    assert changed is False
    assert twice == once


def test_generate_env_content_postgres_url() -> None:
    text = generate_env_content(
        config={"dbName": "wagtail", "dbUser": "wagtail"},
    )
    assert "POSTGRES_DB=wagtail" in text
    assert "POSTGRES_HOST=postgres" in text
    assert "postgres://wagtail:wagtail@postgres:5432/wagtail" in text


def test_setup_rejects_sqlite(tmp_path: Path) -> None:
    config = tmp_path / ".devcontainer" / "create-wagtail-config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        '{"projectName": "mysite", "dbAdapter": "sqlite"}\n',
        encoding="utf-8",
    )
    rc = ensure_wagtail_project(quiet=True, root=tmp_path)
    assert rc == 1
    assert not (tmp_path / "manage.py").exists()


def test_setup_patches_existing_project(tmp_path: Path) -> None:
    (tmp_path / "manage.py").write_text("# manage\n", encoding="utf-8")
    settings = tmp_path / "mysite" / "settings" / "base.py"
    settings.parent.mkdir(parents=True)
    settings.write_text(SQLITE_SETTINGS, encoding="utf-8")
    rc = ensure_wagtail_project(quiet=True, root=tmp_path)
    assert rc == 0
    text = settings.read_text(encoding="utf-8")
    assert "django.db.backends.postgresql" in text
    assert (tmp_path / ".devcontainer" / ".env").is_file()
    assert (tmp_path / ".devcontainer" / "create-wagtail-config.json").is_file()
    assert (tmp_path / ".devcontainer" / "create-wagtail-config.schema.json").is_file()


def test_is_complete_requires_manage_and_settings(tmp_path: Path) -> None:
    assert is_wagtail_project_complete(tmp_path) is False
    (tmp_path / "manage.py").write_text("#\n", encoding="utf-8")
    assert is_wagtail_project_complete(tmp_path) is False
    base = tmp_path / "app" / "settings" / "base.py"
    base.parent.mkdir(parents=True)
    base.write_text("#\n", encoding="utf-8")
    assert is_wagtail_project_complete(tmp_path) is True


def test_remove_generated_docker_files(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.14\n", encoding="utf-8")
    (tmp_path / ".dockerignore").write_text("*\n", encoding="utf-8")
    removed = remove_generated_docker_files(tmp_path)
    assert set(removed) == {"Dockerfile", ".dockerignore"}
    assert not (tmp_path / "Dockerfile").exists()
