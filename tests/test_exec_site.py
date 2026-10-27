"""Container backup uses docker exec and does not read a host media directory."""

from __future__ import annotations

import subprocess
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xgic.cli.wagtail.exec_site import DockerExecSite
from xgic.cli.wagtail.site import SiteError, site_from_namespace


class _Proc:
    def __init__(self, payload: bytes) -> None:
        self.stdout = _Reader(payload)
        self.stderr = _Reader(b"")
        self.returncode = 0

    def wait(self) -> int:
        return 0

    def communicate(self) -> tuple[bytes, bytes]:
        return b"", b""


class _Reader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, _size: int = -1) -> bytes:
        data = self._payload
        self._payload = b""
        return data


def _runner(stdout: str):
    def run(_args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(_args, 0, stdout, "")

    return run


def test_versions_counts_and_media_use_the_named_containers(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        joined = " ".join(args)
        if args[:3] == ["docker", "inspect", "-f"]:
            return subprocess.CompletedProcess(args, 0, "/app\n", "")
        if "os.walk" in joined:
            return subprocess.CompletedProcess(args, 0, "/app\n", "")
        if "SHOW server_version" in joined:
            return subprocess.CompletedProcess(args, 0, "16.4\n", "")
        if "wagtail.__version__" in joined:
            return subprocess.CompletedProcess(args, 0, "7.4.2\n", "")
        return subprocess.CompletedProcess(
            args,
            0,
            "84 objects imported automatically (use -v 2 for details).\n\n8\n8\n21\n0\n",
            "",
        )

    def popen(command, **_kwargs):
        commands.append(command)
        return _Proc(b"tar-bytes")

    site = DockerExecSite(
        web_container="app-a",
        postgres_container="db-a",
        database="cms",
        db_user="cms",
        media_dir="/app/media",
        base_url="http://127.0.0.1:8000",
        runner=runner,
        popen=popen,
    )
    snapshot = site.snapshot()
    media = tmp_path / "media.tar"
    site.write_media(media)
    assert snapshot.wagtail_version == "7.4.2"
    assert snapshot.live_pages == 8
    assert snapshot.all_pages == 8
    assert snapshot.images == 21
    assert snapshot.documents == 0
    count_commands = [
        command
        for command in commands
        if command[:6] == ["docker", "exec", "-w", "/app", "app-a", "python"]
        and "manage.py" in command
        and "shell" in command
    ]
    assert len(count_commands) == 1
    program = count_commands[0][-1]
    assert "Page.objects.live().count()" in program
    assert "Page.objects.count()" in program
    assert "get_image_model().objects.count()" in program
    assert "Document.objects.count()" in program
    assert "DJANGO_SETTINGS_MODULE" not in program
    assert "http://" not in program
    assert "https://" not in program
    assert media.read_bytes() == b"tar-bytes"
    assert ["docker", "exec", "app-a", "tar", "-cf", "-", "-C", "/app/media", "."] in commands
    assert not site.media_dir.exists()


def test_counts_use_the_nested_manage_directory() -> None:
    commands: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        joined = " ".join(args)
        if args[:3] == ["docker", "inspect", "-f"]:
            return subprocess.CompletedProcess(args, 0, "/app\n", "")
        if "os.walk" in joined:
            return subprocess.CompletedProcess(args, 0, "/app/src/project\n", "")
        return subprocess.CompletedProcess(args, 0, "1\n2\n3\n4\n", "")

    site = DockerExecSite(
        web_container="app-a",
        postgres_container="db-a",
        database="cms",
        db_user="cms",
        media_dir="/app/media",
        base_url="http://127.0.0.1:8000",
        runner=runner,
    )
    assert site.current_counts() == (1, 2, 3, 4)
    assert any(
        command[:5] == ["docker", "exec", "-w", "/app/src/project", "app-a"]
        and "manage.py" in command
        for command in commands
    )


def test_counts_reject_anything_other_than_four_integers() -> None:
    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        joined = " ".join(args)
        if args[:3] == ["docker", "inspect", "-f"]:
            return subprocess.CompletedProcess(args, 0, "/app\n", "")
        if "os.walk" in joined:
            return subprocess.CompletedProcess(args, 0, "/app\n", "")
        return subprocess.CompletedProcess(args, 0, "8\n8\n21\n", "")

    site = DockerExecSite(
        web_container="app-a",
        postgres_container="db-a",
        database="cms",
        db_user="cms",
        media_dir="/app/media",
        base_url="http://127.0.0.1:8000",
        runner=runner,
    )
    with pytest.raises(SiteError, match="four counts"):
        site.current_counts()


def test_two_projects_are_selected_from_container_names() -> None:
    first = site_from_namespace(
        Namespace(
            web_container="app-a",
            postgres_container="db-a",
            database="cms",
            db_user="cms",
            media_dir="/app/media",
            base_url="http://127.0.0.1:8000",
            project_dir=None,
            compose_file=None,
            web_service="web",
            postgres_service="postgres",
        )
    )
    second = site_from_namespace(
        Namespace(
            web_container="app-b",
            postgres_container="db-b",
            database="cms",
            db_user="cms",
            media_dir="/app/media",
            base_url="http://127.0.0.1:8000",
            project_dir=None,
            compose_file=None,
            web_service="web",
            postgres_service="postgres",
        )
    )
    assert first.web_container == "app-a"
    assert second.web_container == "app-b"


def test_container_conflicts_come_from_find_output() -> None:
    site = DockerExecSite(
        web_container="app-a",
        postgres_container="db-a",
        database="cms",
        db_user="cms",
        media_dir="/app/media",
        base_url="http://127.0.0.1:8000",
        runner=_runner("kept.jpg\t100\nextra.jpg\t200\n"),
    )
    added, newer = site.container_media_conflicts(
        {"kept.jpg"},
        datetime.fromtimestamp(150, UTC),
    )
    assert added == ["extra.jpg"]
    assert newer == []
