"""Container backup uses docker exec and does not read a host media directory."""

from __future__ import annotations

import subprocess
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path

from xgic.cli.wagtail.exec_site import DockerExecSite
from xgic.cli.wagtail.site import site_from_namespace


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
        if "SHOW server_version" in args:
            return subprocess.CompletedProcess(args, 0, "16.4\n", "")
        if "wagtail.__version__" in "".join(args):
            return subprocess.CompletedProcess(args, 0, "7.4.2\n", "")
        return subprocess.CompletedProcess(args, 0, "4\n2\n1\n", "")

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
    assert snapshot.pages == 4
    assert media.read_bytes() == b"tar-bytes"
    assert ["docker", "exec", "app-a", "tar", "-cf", "-", "-C", "/app/media", "."] in commands
    assert not site.media_dir.exists()


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
