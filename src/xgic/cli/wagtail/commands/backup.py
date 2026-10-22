"""``xgic wagtail backup`` — publish one ``.tar.zst`` pair."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from xgic.cli.wagtail.archive import (
    ArchiveError,
    BackupParts,
    LandingPair,
    payload_sha256,
    sha256_file,
)
from xgic.cli.wagtail.manifest import (
    OMITTED,
    Artifacts,
    BackupManifest,
    Control,
    Counts,
    ManifestError,
    Member,
)
from xgic.cli.wagtail.site import SiteError, SiteGateway


def run_backup(args: argparse.Namespace, site: SiteGateway | None = None) -> int:
    """Create the archive and sidecar. The manifest stays inside the archive."""
    try:
        gateway = site or _site_from_args(args)
        backup_dir = Path(args.backup_dir)
        if args.dry_run:
            return _emit(
                args,
                {
                    "ok": True,
                    "action": "backup",
                    "detail": f"dry-run: would publish a .tar.zst pair in {backup_dir}",
                },
                0,
            )
        snapshot = gateway.snapshot()
        with TemporaryDirectory(prefix="wagtail-backup-") as temporary:
            root = Path(temporary)
            database = root / "database.dump"
            media = root / "media.tar"
            gateway.write_database(database)
            gateway.write_media(media)
            settings = Path(args.settings_file) if args.settings_file else None
            if settings is not None and (not settings.is_file() or settings.is_symlink()):
                raise ArchiveError(f"missing {settings}")
            backup_id = _backup_id(args.project, snapshot.wagtail_version)
            settings_member = None
            hashed = [database, media]
            if settings is not None:
                settings_member = Member(name="settings.file", sha256=sha256_file(settings))
                hashed.append(settings)
            parts = BackupParts(
                backup_id=backup_id,
                database_dump=database,
                media_tar=media,
                settings_file=settings,
                manifest=BackupManifest(
                    created_at=datetime.now(UTC),
                    wagtail_version=snapshot.wagtail_version,
                    postgres_version=snapshot.postgres_version,
                    backup_id=backup_id,
                    payload_sha256=payload_sha256(*hashed),
                    artifacts=Artifacts(
                        database=Member(name="database.dump", sha256=sha256_file(database)),
                        media=Member(name="media.tar", sha256=sha256_file(media)),
                        omitted=list(OMITTED),
                        settings=settings_member,
                    ),
                    counts=Counts(
                        pages=snapshot.pages,
                        images=snapshot.images,
                        documents=snapshot.documents,
                    ),
                    control=Control(
                        inventory=args.inventory or "",
                        node=args.node or "",
                        playbook=args.playbook or "",
                    ),
                ),
            )
            archive = LandingPair(backup_dir).publish(parts)
    except (ArchiveError, ManifestError, SiteError, OSError) as exc:
        return _emit(
            args,
            {"ok": False, "action": "backup", "detail": f"{type(exc).__name__}: {exc}"},
            1,
        )
    return _emit(
        args,
        {"ok": True, "action": "backup", "archive": str(archive), "detail": "published"},
        0,
    )


_PROJECT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _backup_id(project: str, wagtail_version: str) -> str:
    if _PROJECT.fullmatch(project) is None:
        raise ArchiveError("project must be kebab-case")
    safe = wagtail_version.replace("/", "-").replace(" ", "")
    if not safe or "_" in safe:
        raise ArchiveError("version must not contain underscores")
    now = datetime.now(UTC)
    return f"{project}_{now.strftime('%Y%m%dT%H%M%SZ')}_{safe}"


def _site_from_args(args: argparse.Namespace) -> SiteGateway:
    from xgic.cli.wagtail.site import DockerComposeSite

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


def _emit(args: argparse.Namespace, report: dict[str, object], code: int) -> int:
    if getattr(args, "json", False):
        print(json.dumps(report))
    elif report.get("detail"):
        print(report["detail"])
    return code
