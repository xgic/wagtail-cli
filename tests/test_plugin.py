"""Tests for Wagtail CLI plugin registration and usage UX."""

from __future__ import annotations

import argparse
import json

from xgic.cli.wagtail.commands.info import run_info
from xgic.cli.wagtail.plugin import register


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xgic")
    sub = parser.add_subparsers(dest="command")
    register(sub)
    return parser


def test_register_adds_wagtail_group() -> None:
    args = _parser().parse_args(["wagtail", "info"])
    assert args.command == "wagtail"
    assert args.wagtail_command == "info"
    assert callable(args.func)


def test_missing_action_prints_full_usage(capsys) -> None:
    parser = _parser()
    args = parser.parse_args(["wagtail"])
    assert args.wagtail_command is None
    code = args.func(args)
    assert code == 2
    out = capsys.readouterr().out
    assert "usage:" in out.lower()
    assert "info" in out
    assert "the following arguments are required" not in out.lower()


def test_run_info_json(capsys) -> None:
    ns = argparse.Namespace(json=True)
    assert run_info(ns) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["module"] == "xgic.cli.wagtail"
    assert data["package"] == "xgic-wagtail-cli"
    assert data["status"] == "experimental"
    assert "info" in data["commands"]


def test_run_info_human(capsys) -> None:
    ns = argparse.Namespace(json=False)
    assert run_info(ns) == 0
    out = capsys.readouterr().out
    assert "Wagtail CLI" in out
    assert "experimental" in out.lower() or "0.1.0" in out
