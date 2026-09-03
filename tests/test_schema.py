"""Tests for xgic wagtail schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from xgic.cli.app import CommandContext
from xgic.cli.core.environment import EnvironmentContext
from xgic.cli.wagtail.commands.schema import run_schema
from xgic.cli.wagtail.schema import WAGTAIL_CONFIG_SCHEMA, write_schema


def test_schema_enum_is_postgres_only() -> None:
    props = WAGTAIL_CONFIG_SCHEMA["properties"]
    assert isinstance(props, dict)
    adapter = props["dbAdapter"]
    assert isinstance(adapter, dict)
    assert adapter["enum"] == ["postgres"]
    assert "sqlite" not in json.dumps(WAGTAIL_CONFIG_SCHEMA)


def test_write_schema(tmp_path: Path) -> None:
    path = tmp_path / "create-wagtail-config.schema.json"
    written = write_schema(path)
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["properties"]["dbAdapter"]["enum"] == ["postgres"]


def test_run_schema_command(tmp_path: Path) -> None:
    out = tmp_path / "out.schema.json"
    args = argparse.Namespace(output=str(out))
    ctx = CommandContext(env=EnvironmentContext.detect(), args=args)
    assert run_schema(ctx) == 0
    assert out.is_file()
