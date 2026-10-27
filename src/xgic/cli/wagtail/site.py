"""Read a running Wagtail site and write a database dump and media tar."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

_CHUNK = 1024 * 1024


class SiteError(Exception):
    """The site did not provide a version, a count, or a dump."""


@dataclass(frozen=True)
class SiteSnapshot:
    """Versions and database counts recorded in the manifest."""

    wagtail_version: str
    postgres_version: str
    live_pages: int
    all_pages: int
    images: int
    documents: int


class CommandRunner(Protocol):
    """Run one command and return its result."""

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run ``args``."""


class SiteGateway(Protocol):
    """What backup and restore need from a Wagtail site."""

    def snapshot(self) -> SiteSnapshot:
        """Return versions and database counts."""

    def write_database(self, dest: Path) -> None:
        """Write a custom-format ``pg_dump`` with compression left to zstd."""

    def write_media(self, dest: Path) -> None:
        """Write an uncompressed tar of the media directory."""

    def restore_database(self, dump: Path) -> None:
        """Restore ``database.dump`` into PostgreSQL."""

    def restore_media(self, media_tar: Path) -> None:
        """Replace the media directory from ``media.tar``."""

    def merge_media(self, media_tar: Path) -> None:
        """Copy archive files onto the media directory and keep the rest."""

    @property
    def media_dir(self) -> Path:
        """Live media directory."""

    def current_versions(self) -> tuple[str, str]:
        """Return the running Wagtail version and ``SHOW server_version``."""

    def current_counts(self) -> tuple[int, int, int, int]:
        """Return live pages, all pages, images, and documents."""


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
        runner: CommandRunner | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.compose_file = compose_file
        self.web_service = web_service
        self.postgres_service = postgres_service
        self.database = database
        self.db_user = db_user
        self.media_dir = media_dir
        self.base_url = base_url.rstrip("/")
        self._runner: CommandRunner = runner or _run_text

    def snapshot(self) -> SiteSnapshot:
        wagtail_version, postgres_version = self.current_versions()
        live_pages, all_pages, images, documents = self.current_counts()
        return SiteSnapshot(
            wagtail_version=wagtail_version,
            postgres_version=postgres_version,
            live_pages=live_pages,
            all_pages=all_pages,
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

    def current_counts(self) -> tuple[int, int, int, int]:
        """Compose mode has no database session. Pass ``--web-container``."""
        raise SiteError("counts require --web-container")

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
        if self.media_dir.is_symlink():
            raise SiteError("refusing to replace a symlink")
        staging = self.media_dir.with_name(self.media_dir.name + ".restore")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, mode=0o700)
        completed = self._run(["tar", "-xf", str(media_tar), "-C", str(staging)])
        if completed.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            detail = (completed.stderr or "").strip() or "media extract failed"
            raise SiteError(detail)
        if self.media_dir.exists():
            shutil.rmtree(self.media_dir)
        os.replace(staging, self.media_dir)

    def merge_media(self, media_tar: Path) -> None:
        if self.media_dir.is_symlink():
            raise SiteError("refusing to merge through a symlink")
        self.media_dir.mkdir(parents=True, exist_ok=True)
        completed = self._run(["tar", "-xf", str(media_tar), "-C", str(self.media_dir)])
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or "media merge failed"
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
        return self._runner(args)


def media_names(media_tar: Path) -> set[str]:
    """Return file paths stored in an uncompressed media tar."""
    completed = subprocess.run(
        ["tar", "-tf", str(media_tar)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "cannot list media.tar"
        raise SiteError(detail)
    names: set[str] = set()
    for line in completed.stdout.splitlines():
        name = line.strip().removeprefix("./")
        if name and not name.endswith("/"):
            names.add(name)
    return names


def media_conflicts(
    media_dir: Path,
    archive_names: set[str],
    created_at: datetime,
) -> tuple[list[str], list[str]]:
    """Return files added after the backup, then files edited after it.

    A path only on disk was added. A path in both whose modification time
    is newer than ``created_at`` was edited. Deleted files are not listed.
    """
    added: list[str] = []
    newer: list[str] = []
    if not media_dir.is_dir():
        return added, newer
    moment = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    for path in sorted(media_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(media_dir).as_posix()
        if rel not in archive_names:
            added.append(rel)
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if mtime > moment:
            newer.append(rel)
    return added, newer


def _run_text(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def site_from_namespace(args: object) -> SiteGateway:
    """Use container names when they are set, otherwise Compose on disk."""
    web = getattr(args, "web_container", None) or ""
    postgres = getattr(args, "postgres_container", None) or ""
    if web and postgres:
        from xgic.cli.wagtail.exec_site import DockerExecSite

        return DockerExecSite(
            web_container=web,
            postgres_container=postgres,
            database=args.database,
            db_user=args.db_user,
            media_dir=args.media_dir,
            base_url=args.base_url,
        )
    return DockerComposeSite(
        project_dir=Path(args.project_dir or Path.cwd()),
        compose_file=args.compose_file,
        web_service=args.web_service,
        postgres_service=args.postgres_service,
        database=args.database,
        db_user=args.db_user,
        media_dir=Path(args.media_dir),
        base_url=args.base_url,
    )
