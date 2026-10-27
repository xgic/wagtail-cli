"""Read and restore a Wagtail site through ``docker exec``.

The application container already has the media files. This path does not
mount that volume into the process that runs the command.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from xgic.cli.wagtail.site import CommandRunner, SiteError, SiteSnapshot, _run_text

_CHUNK = 1024 * 1024

_COUNT_PROGRAM = """
from wagtail.models import Page
from wagtail.images import get_image_model
from wagtail.documents.models import Document
print(Page.objects.live().count())
print(Page.objects.count())
print(get_image_model().objects.count())
print(Document.objects.count())
"""

# manage.py selects the project settings. It lives in the container working
# directory, or in the one project directory under that working directory.
_MANAGE_DIRECTORY_PROGRAM = r"""
import os
from pathlib import Path
root = Path.cwd()
if (root / "manage.py").is_file():
    print(root)
    raise SystemExit(0)
skip = {
    ".git",
    ".venv",
    "media",
    "node_modules",
    "site-packages",
    "static",
    "static_collected",
    "venv",
}
matches = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [name for name in dirnames if name not in skip]
    if "manage.py" in filenames:
        matches.append(Path(dirpath))
if len(matches) != 1:
    raise SystemExit(f"manage.py count {len(matches)}")
print(matches[0])
"""


class DockerExecSite:
    """A running Wagtail container and its database container."""

    def __init__(
        self,
        *,
        web_container: str,
        postgres_container: str,
        database: str,
        db_user: str,
        media_dir: str,
        base_url: str,
        runner: CommandRunner | None = None,
        popen: object | None = None,
    ) -> None:
        self.web_container = web_container
        self.postgres_container = postgres_container
        self.database = database
        self.db_user = db_user
        self.media_path = media_dir
        self.base_url = base_url.rstrip("/")
        self._runner = runner or _run_text
        self._popen = popen or subprocess.Popen

    @property
    def media_dir(self) -> Path:
        """Host path is unused. Conflict checks run inside the container."""
        return Path("/docker-exec") / "not-a-host-directory"

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
        wagtail = self._text(
            [
                "docker",
                "exec",
                self.web_container,
                "python",
                "-c",
                "import wagtail; print(wagtail.__version__)",
            ]
        )
        postgres = self._text(
            [
                "docker",
                "exec",
                self.postgres_container,
                "psql",
                "-U",
                self.db_user,
                "-d",
                self.database,
                "-tAc",
                "SHOW server_version",
            ]
        )
        return wagtail.strip(), postgres.strip()

    def current_counts(self) -> tuple[int, int, int, int]:
        workdir = self._text(
            [
                "docker",
                "inspect",
                "-f",
                "{{.Config.WorkingDir}}",
                self.web_container,
            ]
        ).strip() or "/"
        manage_dir = self._manage_directory(workdir)
        text = self._text(
            [
                "docker",
                "exec",
                "-w",
                manage_dir,
                self.web_container,
                "python",
                "manage.py",
                "shell",
                "-c",
                _COUNT_PROGRAM,
            ]
        )
        lines = [line.strip() for line in text.splitlines() if line.strip().isdigit()]
        if len(lines) != 4:
            raise SiteError("ValueError: container did not return four counts")
        live_pages, all_pages, images, documents = (int(line) for line in lines)
        return live_pages, all_pages, images, documents

    def _manage_directory(self, workdir: str) -> str:
        text = self._text(
            [
                "docker",
                "exec",
                "-w",
                workdir,
                self.web_container,
                "python",
                "-c",
                _MANAGE_DIRECTORY_PROGRAM,
            ]
        )
        found = [line.strip() for line in text.splitlines() if line.strip()]
        if len(found) != 1 or not found[0].startswith("/"):
            raise SiteError("ValueError: container did not name one manage.py directory")
        return found[0]

    def write_database(self, dest: Path) -> None:
        self._stream(
            [
                "docker",
                "exec",
                self.postgres_container,
                "pg_dump",
                "-Fc",
                "-Z",
                "0",
                "-U",
                self.db_user,
                "-d",
                self.database,
            ],
            dest,
        )

    def write_media(self, dest: Path) -> None:
        self._stream(
            [
                "docker",
                "exec",
                self.web_container,
                "tar",
                "-cf",
                "-",
                "-C",
                self.media_path,
                ".",
            ],
            dest,
        )

    def restore_database(self, dump: Path) -> None:
        self._stream_in(
            [
                "docker",
                "exec",
                "-i",
                self.postgres_container,
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--exit-on-error",
                "-U",
                self.db_user,
                "-d",
                self.database,
            ],
            dump,
        )

    def restore_media(self, media_tar: Path) -> None:
        self._clear_media()
        self._extract_media(media_tar)

    def merge_media(self, media_tar: Path) -> None:
        self._extract_media(media_tar)

    def container_media_conflicts(
        self,
        archive_names: set[str],
        created_at: datetime,
    ) -> tuple[list[str], list[str]]:
        """Compare live container files with the archive listing."""
        text = self._text(
            [
                "docker",
                "exec",
                self.web_container,
                "find",
                self.media_path,
                "-type",
                "f",
                "-printf",
                "%P\\t%T@\\n",
            ]
        )
        moment = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
        added: list[str] = []
        newer: list[str] = []
        for line in text.splitlines():
            name, separator, stamp = line.partition("\t")
            if not separator or not name or name.endswith("/"):
                continue
            if name not in archive_names:
                added.append(name)
                continue
            try:
                mtime = datetime.fromtimestamp(float(stamp), UTC)
            except ValueError:
                continue
            if mtime > moment:
                newer.append(name)
        return sorted(added), sorted(newer)

    def _clear_media(self) -> None:
        script = (
            'if [ -L "$1" ]; then echo "refusing to replace a symlink" >&2; exit 3; fi; '
            'if [ ! -d "$1" ]; then echo "media directory missing" >&2; exit 4; fi; '
            'find "$1" -mindepth 1 -delete'
        )
        self._text(
            [
                "docker",
                "exec",
                self.web_container,
                "sh",
                "-c",
                script,
                "sh",
                self.media_path,
            ]
        )

    def _extract_media(self, media_tar: Path) -> None:
        self._stream_in(
            [
                "docker",
                "exec",
                "-i",
                self.web_container,
                "tar",
                "-xf",
                "-",
                "-C",
                self.media_path,
            ],
            media_tar,
        )

    def _text(self, args: list[str]) -> str:
        completed = self._runner(args)
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or "docker exec failed"
            raise SiteError(detail)
        return completed.stdout or ""

    def _stream(self, command: list[str], dest: Path) -> None:
        proc = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdout is not None
        try:
            with dest.open("wb") as handle:
                for chunk in iter(lambda: proc.stdout.read(_CHUNK), b""):
                    handle.write(chunk)
        finally:
            stderr = proc.stderr.read() if proc.stderr is not None else b""
            code = proc.wait()
        if code != 0:
            detail = stderr.decode(errors="replace").strip() or "docker exec failed"
            raise SiteError(detail)

    def _stream_in(self, command: list[str], source: Path) -> None:
        with source.open("rb") as handle:
            proc = self._popen(
                command,
                stdin=handle,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            detail = stderr.decode(errors="replace").strip() or "docker exec failed"
            raise SiteError(detail)
