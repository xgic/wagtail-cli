"""``xgic wagtail backup`` — publish one ``.tar.zst`` pair."""

from __future__ import annotations

import argparse
import json
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
            backup_id = _backup_id(snapshot.wagtail_version)
            settings_member = None
            if settings is not None:
                settings_member = Member(name="settings.file", sha256=sha256_file(settings))
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
                    archive_sha256=payload_sha256(
                        BackupParts(
                            backup_id=backup_id,
                            database_dump=database,
                            media_tar=media,
                            settings_file=settings,
                            manifest=_placeholder_manifest(backup_id),
                        )
                    ),
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


def _placeholder_manifest(backup_id: str) -> BackupManifest:
    """Unused by the payload hash. Present so BackupParts can be constructed."""
    return BackupManifest(
        created_at=datetime.now(UTC),
        wagtail_version="0",
        postgres_version="0",
        backup_id=backup_id,
        archive_sha256="0" * 64,
        artifacts=Artifacts(
            database=Member(name="database.dump", sha256="0" * 64),
            media=Member(name="media.tar", sha256="0" * 64),
            omitted=list(OMITTED),
        ),
        counts=Counts(pages=0, images=0, documents=0),
    )


def _backup_id(wagtail_version: str) -> str:
    now = datetime.now(UTC)
    safe = wagtail_version.replace("/", "-").replace(" ", "")
    return f"{int(now.timestamp())}_{now.strftime('%Y_%m_%d')}_{safe}"


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
