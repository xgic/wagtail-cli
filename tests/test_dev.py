"""Tests for ``xgic wagtail dev``."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from xgic.cli.wagtail.commands.dev import run_dev


def _ctx(*, quiet: bool = True) -> SimpleNamespace:
    return SimpleNamespace(args=argparse.Namespace(quiet=quiet))


def test_dev_requires_setup(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_dev(_ctx()) == 2
    err = capsys.readouterr()
    text = err.out + err.err
    assert "xgic wagtail setup" in text


def test_dev_waits_for_postgres(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text("# manage\n", encoding="utf-8")
    settings = tmp_path / "mysite" / "settings"
    settings.mkdir(parents=True)
    (settings / "base.py").write_text("# settings\n", encoding="utf-8")
    monkeypatch.setattr(
        "xgic.cli.wagtail.commands.dev._wait_for_postgres",
        lambda *args, **kwargs: False,
    )
    assert run_dev(_ctx()) == 1
    captured = capsys.readouterr()
    assert "PostgreSQL" in (captured.out + captured.err)


def test_dev_migrate_then_runserver(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text("# manage\n", encoding="utf-8")
    settings = tmp_path / "mysite" / "settings"
    settings.mkdir(parents=True)
    (settings / "base.py").write_text("# settings\n", encoding="utf-8")
    monkeypatch.setattr(
        "xgic.cli.wagtail.commands.dev._wait_for_postgres",
        lambda *args, **kwargs: True,
    )

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0)

    class FakeProc:
        def wait(self, timeout=None):
            return 0

        def send_signal(self, *_args):
            return None

        def kill(self):
            return None

    def fake_popen(cmd, **kwargs):
        calls.append(list(cmd))
        return FakeProc()

    monkeypatch.setattr("xgic.cli.wagtail.commands.dev.subprocess.run", fake_run)
    monkeypatch.setattr("xgic.cli.wagtail.commands.dev.subprocess.Popen", fake_popen)
    assert run_dev(_ctx()) == 0
    assert any("migrate" in c for c in calls)
    assert any("runserver" in c for c in calls)
