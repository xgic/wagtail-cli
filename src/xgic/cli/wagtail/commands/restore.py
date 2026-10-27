"""``xgic wagtail restore`` — restore one verified ``.tar.zst`` pair."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from xgic.cli.wagtail.archive import ArchiveError, LandingPair, sha256_file
from xgic.cli.wagtail.manifest import ManifestError
from xgic.cli.wagtail.site import SiteError, SiteGateway, media_conflicts, media_names


def run_restore(args: argparse.Namespace, site: SiteGateway | None = None) -> int:
    """Check the sidecar and manifest, then restore when ``--yes`` is set."""
    try:
        gateway = site or _site_from_args(args)
        backup_dir = Path(args.backup_dir)
        landing = LandingPair(backup_dir)
        archive = Path(args.archive) if args.archive else landing.newest()
        if not archive.is_absolute():
            archive = backup_dir / archive
        manifest = landing.manifest_of(archive)
        wagtail_version, postgres_version = gateway.current_versions()
        if wagtail_version != manifest.wagtail_version:
            raise ArchiveError(
                f"wagtail_version {wagtail_version} != {manifest.wagtail_version}"
            )
        if postgres_version != manifest.postgres_version:
            raise ArchiveError(
                f"postgres_version {postgres_version} != {manifest.postgres_version}"
            )
        extract = backup_dir / f".{archive.name}.extract"
        manifest, extracted = landing.open(archive, extract)
        try:
            names = media_names(extracted / "media.tar")
            conflicts = getattr(gateway, "container_media_conflicts", None)
            if conflicts is not None:
                added, newer = conflicts(names, manifest.created_at)
            else:
                added, newer = media_conflicts(
                    gateway.media_dir,
                    names,
                    manifest.created_at,
                )
            if args.media == "check" and (added or newer):
                raise ArchiveError(_media_warning(added, newer))
            if args.dry_run:
                detail = f"dry-run: {archive.name} matches the running versions"
                if added or newer:
                    detail = f"{detail}; {_media_warning(added, newer)}"
                return _emit(args, {"ok": True, "action": "restore", "detail": detail}, 0)
            if not args.yes:
                raise ArchiveError("restore requires --yes")
            gateway.restore_database(extracted / "database.dump")
            if args.media == "merge":
                gateway.merge_media(extracted / "media.tar")
            else:
                gateway.restore_media(extracted / "media.tar")
            if args.settings_dest:
                settings = extracted / "settings.file"
                if not settings.is_file():
                    raise ArchiveError("archive has no settings.file")
                _copy_private(settings, Path(args.settings_dest))
            live_pages, all_pages, images, documents = gateway.current_counts()
            actual = (live_pages, all_pages, images, documents)
            expected = (
                manifest.counts.live_pages,
                manifest.counts.all_pages,
                manifest.counts.images,
                manifest.counts.documents,
            )
            if actual != expected:
                raise ArchiveError(
                    "counts "
                    f"{live_pages},{all_pages},{images},{documents} != "
                    f"{manifest.counts.live_pages},"
                    f"{manifest.counts.all_pages},"
                    f"{manifest.counts.images},"
                    f"{manifest.counts.documents}"
                )
        finally:
            shutil.rmtree(extracted, ignore_errors=True)
    except (ArchiveError, ManifestError, SiteError, OSError) as exc:
        return _emit(
            args,
            {"ok": False, "action": "restore", "detail": f"{type(exc).__name__}: {exc}"},
            1,
        )
    return _emit(args, {"ok": True, "action": "restore", "detail": "restored"}, 0)


def _media_warning(added: list[str], newer: list[str]) -> str:
    lines = ["media files were added or edited after the backup"]
    if added:
        lines.append("added: " + ", ".join(added))
    if newer:
        lines.append("newer: " + ", ".join(newer))
    return "; ".join(lines)


def _copy_private(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as source, dest.open("wb") as target:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            target.write(chunk)
    os.chmod(dest, 0o600)
    if sha256_file(dest) != sha256_file(src):
        dest.unlink(missing_ok=True)
        raise ArchiveError("settings copy does not match the archive")


def _site_from_args(args: argparse.Namespace) -> SiteGateway:
    from xgic.cli.wagtail.site import site_from_namespace

    return site_from_namespace(args)


def _emit(args: argparse.Namespace, report: dict[str, object], code: int) -> int:
    if getattr(args, "json", False):
        print(json.dumps(report))
    elif report.get("detail"):
        print(report["detail"])
    return code
