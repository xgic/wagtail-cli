"""Publish and open one Wagtail backup pair.

The pair is one ``.tar.zst`` and a sibling ``.tar.zst.sha256``. The archive
holds ``database.dump``, ``media.tar``, an optional settings file, and
``backup-manifest.json``. There is no manifest file beside the archive.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from xgic.cli.wagtail.manifest import BackupManifest, ManifestError, parse_manifest

_CHUNK = 1024 * 1024
_SECRET_MODE = 0o600


class ArchiveError(Exception):
    """The backup pair is missing a member or fails a check."""


class CommandRunner(Protocol):
    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one command and return its result."""


@dataclass(frozen=True)
class BackupParts:
    """Files packed into the archive."""

    backup_id: str
    database_dump: Path
    media_tar: Path
    settings_file: Path | None
    manifest: BackupManifest


def sha256_file(path: Path) -> str:
    """Hash a file in 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_sha256(parts: BackupParts) -> str:
    """Hash ``database.dump``, then ``media.tar``, then the settings file."""
    digest = hashlib.sha256()
    paths = [parts.database_dump, parts.media_tar]
    if parts.settings_file is not None:
        paths.append(parts.settings_file)
    for path in paths:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK), b""):
                digest.update(chunk)
    return digest.hexdigest()


def sidecar_line(digest: str, archive_name: str) -> str:
    return f"{digest}  {archive_name}\n"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _copy_bytes(src: Path, dest: Path) -> None:
    with src.open("rb") as source, dest.open("wb") as target:
        for chunk in iter(lambda: source.read(_CHUNK), b""):
            target.write(chunk)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    os.chmod(path, _SECRET_MODE)


class LandingPair:
    """Create and open the landing pair for one Wagtail backup."""

    def __init__(self, output_dir: Path, runner: CommandRunner | None = None) -> None:
        self.output_dir = output_dir
        self._runner = runner or _run

    def publish(self, parts: BackupParts) -> Path:
        """Write the pair. Source files are not modified."""
        self._require_files(parts)
        if parts.manifest.archive_sha256 != payload_sha256(parts):
            raise ArchiveError("manifest payload digest does not match the members")
        if parts.manifest.artifacts.database.sha256 != sha256_file(parts.database_dump):
            raise ArchiveError("manifest digest does not match database.dump")
        if parts.manifest.artifacts.media.sha256 != sha256_file(parts.media_tar):
            raise ArchiveError("manifest digest does not match media.tar")
        archive_name = f"{parts.backup_id}.tar.zst"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        archive = self.output_dir / archive_name
        partial = self.output_dir / f"{archive_name}.partial"
        sidecar_partial = self.output_dir / f"{archive_name}.sha256.partial"
        sidecar = archive.with_name(archive.name + ".sha256")
        staging = self.output_dir / f".{archive_name}.staging"
        try:
            self._stage(parts, staging)
            self._tar_create(partial, staging)
            os.chmod(partial, _SECRET_MODE)
            _write_text(sidecar_partial, sidecar_line(sha256_file(partial), archive.name))
            os.replace(partial, archive)
            try:
                os.replace(sidecar_partial, sidecar)
            except OSError:
                archive.unlink(missing_ok=True)
                raise
            os.chmod(archive, _SECRET_MODE)
            os.chmod(sidecar, _SECRET_MODE)
        finally:
            partial.unlink(missing_ok=True)
            sidecar_partial.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)
        return archive

    def manifest_of(self, archive: Path) -> BackupManifest:
        """Validate the sidecar and the inner manifest without a full extract."""
        if not archive.is_file() or archive.is_symlink():
            raise ArchiveError(f"missing {archive.name}")
        self.verify_sidecar(archive)
        listed = self._runner(["tar", "--zstd", "-tf", str(archive)])
        if listed.returncode != 0:
            raise ArchiveError(listed.stderr.strip() or "cannot list archive")
        member = next(
            (
                name
                for name in listed.stdout.splitlines()
                if Path(name).name == "backup-manifest.json"
            ),
            None,
        )
        if member is None:
            raise ArchiveError("archive is missing backup-manifest.json")
        completed = self._runner(
            ["tar", "--zstd", "-xOf", str(archive), member]
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "cannot read backup-manifest.json"
            raise ArchiveError(detail)
        try:
            return parse_manifest(completed.stdout)
        except ManifestError as exc:
            raise ArchiveError(str(exc)) from exc

    def open(self, archive: Path, dest_dir: Path) -> tuple[BackupManifest, Path]:
        """Check the sidecar, extract, and return the manifest and extract directory."""
        if dest_dir.is_symlink():
            raise ArchiveError("refusing to extract through a symlink")
        manifest = self.manifest_of(archive)
        staging = dest_dir.with_name(dest_dir.name + ".partial")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, mode=0o700)
        try:
            completed = self._runner(
                ["tar", "--zstd", "-xf", str(archive), "-C", str(staging)]
            )
            if completed.returncode != 0:
                raise ArchiveError(completed.stderr.strip() or "extract failed")
            self._require_members(staging, manifest)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        os.replace(staging, dest_dir)
        os.chmod(dest_dir, 0o700)
        return manifest, dest_dir

    def newest(self) -> Path:
        found = [
            path
            for path in self.output_dir.glob("*.tar.zst")
            if path.is_file() and not path.is_symlink()
        ]
        if not found:
            raise ArchiveError(f"no .tar.zst pair in {self.output_dir}")
        found.sort(key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
        return found[0]

    def verify_sidecar(self, archive: Path) -> None:
        sidecar = archive.with_name(archive.name + ".sha256")
        if not sidecar.is_file() or sidecar.is_symlink():
            raise ArchiveError(f"missing sidecar for {archive.name}")
        text = sidecar.read_text(encoding="utf-8")
        if text != sidecar_line(sha256_file(archive), archive.name):
            raise ArchiveError(f"sidecar does not match {archive.name}")

    def _require_files(self, parts: BackupParts) -> None:
        for path in (parts.database_dump, parts.media_tar):
            if not path.is_file() or path.is_symlink():
                raise ArchiveError(f"missing {path.name}")
        if parts.settings_file is not None and (
            not parts.settings_file.is_file() or parts.settings_file.is_symlink()
        ):
            raise ArchiveError(f"missing {parts.settings_file.name}")

    def _stage(self, parts: BackupParts, staging: Path) -> None:
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, mode=0o700)
        _copy_bytes(parts.database_dump, staging / "database.dump")
        _copy_bytes(parts.media_tar, staging / "media.tar")
        if parts.settings_file is not None:
            _copy_bytes(parts.settings_file, staging / "settings.file")
        _write_text(staging / "backup-manifest.json", parts.manifest.to_json())

    def _tar_create(self, partial: Path, staging: Path) -> None:
        completed = self._runner(
            ["tar", "--zstd", "-cf", str(partial), "-C", str(staging), "."]
        )
        if completed.returncode != 0:
            raise ArchiveError(completed.stderr.strip() or "tar --zstd failed")

    def _require_members(self, dest: Path, manifest: BackupManifest) -> None:
        for name in ("database.dump", "media.tar", "backup-manifest.json"):
            path = dest / name
            if not path.is_file() or path.is_symlink():
                raise ArchiveError(f"archive is missing {name}")
        if sha256_file(dest / "database.dump") != manifest.artifacts.database.sha256:
            raise ArchiveError("database.dump does not match the manifest")
        if sha256_file(dest / "media.tar") != manifest.artifacts.media.sha256:
            raise ArchiveError("media.tar does not match the manifest")
        digest = hashlib.sha256()
        paths = [dest / "database.dump", dest / "media.tar"]
        if manifest.artifacts.settings is not None:
            paths.append(dest / "settings.file")
        for path in paths:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(_CHUNK), b""):
                    digest.update(chunk)
        if digest.hexdigest() != manifest.archive_sha256:
            raise ArchiveError("payload digest does not match the manifest")
        if manifest.artifacts.settings is not None:
            settings = dest / "settings.file"
            if not settings.is_file():
                raise ArchiveError("archive is missing settings.file")
            if sha256_file(settings) != manifest.artifacts.settings.sha256:
                raise ArchiveError("settings.file does not match the manifest")
