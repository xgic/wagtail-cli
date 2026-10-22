"""Read a running Wagtail site and write a database dump and media tar."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_CHUNK = 1024 * 1024


class SiteError(Exception):
    """The site did not provide a version, a count, or a dump."""


@dataclass(frozen=True)
class SiteSnapshot:
    """Versions and API counts recorded in the manifest."""

    wagtail_version: str
    postgres_version: str
    pages: int
    images: int
    documents: int


class SiteGateway(Protocol):
    """What backup and restore need from a Wagtail site."""

    def snapshot(self) -> SiteSnapshot:
        """Return versions and API counts."""

    def write_database(self, dest: Path) -> None:
        """Write a custom-format ``pg_dump`` with compression left to zstd."""

    def write_media(self, dest: Path) -> None:
        """Write an uncompressed tar of the media directory."""

    def restore_database(self, dump: Path) -> None:
        """Restore ``database.dump`` into PostgreSQL."""

    def restore_media(self, media_tar: Path) -> None:
        """Replace the media directory from ``media.tar``."""

    def current_versions(self) -> tuple[str, str]:
        """Return the running Wagtail version and ``SHOW server_version``."""

    def current_counts(self) -> tuple[int, int, int]:
        """Return pages, images, and documents from the API."""


def count_from_payload(payload: object, url: str) -> int:
    """Read ``meta.total_count`` from one Wagtail API listing."""
    if not isinstance(payload, dict):
        raise SiteError(f"TypeError: {url} did not return an object")
    meta = payload.get("meta")
    if not isinstance(meta, dict) or "total_count" not in meta:
        raise SiteError(f"ValueError: {url} is missing meta.total_count")
    try:
        return int(meta["total_count"])
    except (TypeError, ValueError) as exc:
        raise SiteError(f"{type(exc).__name__}: {url} meta.total_count") from exc


def fetch_count(url: str, opener: urllib.request.OpenerDirector | None = None) -> int:
    """GET one listing endpoint and return ``meta.total_count``."""
    open_url = urllib.request.urlopen if opener is None else opener.open
    try:
        with open_url(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.URLError as exc:
        raise SiteError(f"URLError: {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SiteError(f"JSONDecodeError: {url}: {exc}") from exc
    return count_from_payload(payload, url)


class DockerComposeSite:
    """A Wagtail Compose project on this host."""

    def __init__(
        self,
        *,
        project_dir: Path,
        compose_file: str | None,
        web_service: str,
        postgres_service: str,
        database: str,
        db_user: str,
        media_dir: Path,
        base_url: str,
        runner: object | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.compose_file = compose_file
        self.web_service = web_service
        self.postgres_service = postgres_service
        self.database = database
        self.db_user = db_user
        self.media_dir = media_dir
        self.base_url = base_url.rstrip("/")
        self._runner = runner

    def snapshot(self) -> SiteSnapshot:
        wagtail_version, postgres_version = self.current_versions()
        pages, images, documents = self.current_counts()
        return SiteSnapshot(
            wagtail_version=wagtail_version,
            postgres_version=postgres_version,
            pages=pages,
            images=images,
            documents=documents,
        )

    def current_versions(self) -> tuple[str, str]:
        wagtail = self._exec(
            self.web_service,
            ["python", "-c", "import wagtail; print(wagtail.__version__)"],
        )
        postgres = self._exec(
            self.postgres_service,
            [
                "psql",
                "-U",
                self.db_user,
                "-d",
                self.database,
                "-tAc",
                "SHOW server_version",
            ],
        )
        return wagtail.strip(), postgres.strip()

    def current_counts(self) -> tuple[int, int, int]:
        return (
            fetch_count(f"{self.base_url}/api/v2/pages/"),
            fetch_count(f"{self.base_url}/api/v2/images/"),
            fetch_count(f"{self.base_url}/api/v2/documents/"),
        )

    def write_database(self, dest: Path) -> None:
        command = self._compose(
            [
                "exec",
                "-T",
                self.postgres_service,
                "pg_dump",
                "-Fc",
                "-Z",
                "0",
                "-U",
                self.db_user,
                "-d",
                self.database,
            ]
        )
        self._stream_stdout(command, dest)

    def write_media(self, dest: Path) -> None:
        if not self.media_dir.is_dir():
            raise SiteError(f"FileNotFoundError: media directory {self.media_dir}")
        completed = self._run(
            ["tar", "-cf", str(dest), "-C", str(self.media_dir), "."]
        )
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or "tar failed"
            raise SiteError(detail)

    def restore_database(self, dump: Path) -> None:
        command = self._compose(
            [
                "exec",
                "-T",
                self.postgres_service,
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--exit-on-error",
                "-U",
                self.db_user,
                "-d",
                self.database,
            ]
        )
        with dump.open("rb") as handle:
            proc = subprocess.run(command, stdin=handle, capture_output=True, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.decode(errors="replace").strip() or "pg_restore failed"
            raise SiteError(detail)

    def restore_media(self, media_tar: Path) -> None:
        self.media_dir.mkdir(parents=True, exist_ok=True)
        completed = self._run(
            ["tar", "-xf", str(media_tar), "-C", str(self.media_dir)]
        )
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or "media extract failed"
            raise SiteError(detail)

    def _exec(self, service: str, args: list[str]) -> str:
        completed = self._run(self._compose(["exec", "-T", service, *args]))
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or f"{service} command failed"
            raise SiteError(detail)
        return completed.stdout or ""

    def _compose(self, args: list[str]) -> list[str]:
        command = ["docker", "compose"]
        if self.compose_file:
            command.extend(["-f", self.compose_file])
        command.extend(["--project-directory", str(self.project_dir)])
        command.extend(args)
        return command

    def _stream_stdout(self, command: list[str], dest: Path) -> None:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdout is not None
        try:
            with dest.open("wb") as handle:
                for chunk in iter(lambda: proc.stdout.read(_CHUNK), b""):
                    handle.write(chunk)
        finally:
            stderr = proc.stderr.read() if proc.stderr is not None else b""
            code = proc.wait()
        if code != 0:
            detail = stderr.decode(errors="replace").strip() or "pg_dump failed"
            raise SiteError(detail)

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if self._runner is not None:
            return self._runner(args)  # type: ignore[operator]
        return subprocess.run(args, capture_output=True, text=True, check=False)
