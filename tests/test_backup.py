"""Wagtail backup and restore pair."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from xgic.cli.wagtail.archive import LandingPair
from xgic.cli.wagtail.commands.backup import run_backup
from xgic.cli.wagtail.commands.restore import run_restore
from xgic.cli.wagtail.manifest import parse_manifest
from xgic.cli.wagtail.site import SiteSnapshot


class FakeSite:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.media = root / "media"
        self.media.mkdir()
        (self.media / "photo.jpg").write_bytes(b"jpeg-bytes")
        self.dump = b"PGDMP-fake-dump"
        self.snapshot_value = SiteSnapshot(
            wagtail_version="8.0.1",
            postgres_version="16.4",
            live_pages=6,
            all_pages=7,
            images=2,
            documents=1,
        )
        self.restored_dump: Path | None = None
        self.restored_media = False
        self.merged_media = False
        self.settings_written: Path | None = None
        self.counts = (6, 7, 2, 1)

    def snapshot(self) -> SiteSnapshot:
        return self.snapshot_value

    def write_database(self, dest: Path) -> None:
        dest.write_bytes(self.dump)

    def write_media(self, dest: Path) -> None:
        import subprocess

        subprocess.run(
            ["tar", "-cf", str(dest), "-C", str(self.media), "."],
            check=True,
        )

    def restore_database(self, dump: Path) -> None:
        self.restored_dump = dump

    def restore_media(self, media_tar: Path) -> None:
        self.restored_media = True
        media_tar.read_bytes()

    def merge_media(self, media_tar: Path) -> None:
        self.merged_media = True
        media_tar.read_bytes()

    @property
    def media_dir(self) -> Path:
        return self.media

    def current_versions(self) -> tuple[str, str]:
        return self.snapshot_value.wagtail_version, self.snapshot_value.postgres_version

    def current_counts(self) -> tuple[int, int, int, int]:
        return self.counts


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "project": "wagtail-example",
        "backup_dir": str(tmp_path / "backups"),
        "base_url": "http://127.0.0.1:8000",
        "project_dir": None,
        "compose_file": None,
        "web_service": "web",
        "postgres_service": "postgres",
        "database": "wagtail",
        "db_user": "wagtail",
        "media_dir": "media",
        "json": True,
        "settings_file": None,
        "inventory": "",
        "node": "",
        "playbook": "",
        "dry_run": False,
        "archive": None,
        "settings_dest": None,
        "yes": False,
        "media": "check",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    code = run_backup(_args(tmp_path, dry_run=True), site)
    assert code == 0
    assert not (tmp_path / "backups").exists()


def test_backup_publishes_pair_with_inner_manifest(tmp_path: Path, capsys) -> None:
    site = FakeSite(tmp_path)
    code = run_backup(_args(tmp_path), site)
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    archive = Path(report["archive"])
    assert archive.suffixes[-2:] == [".tar", ".zst"]
    sidecar = archive.with_name(archive.name + ".sha256")
    assert sidecar.read_text(encoding="utf-8").endswith(f"  {archive.name}\n")
    assert list(archive.parent.glob("*.backup-manifest.json")) == []
    manifest = LandingPair(archive.parent).manifest_of(archive)
    assert manifest.wagtail_version == "8.0.1"
    assert manifest.postgres_version == "16.4"
    assert manifest.counts.live_pages == 6
    assert manifest.counts.all_pages == 7
    assert manifest.counts.images == 2
    assert manifest.counts.documents == 1
    assert manifest.artifacts.omitted == ["search_index", "cache"]
    assert manifest.artifacts.database.name == "database.dump"
    listed = subprocess.run(
        ["tar", "--zstd", "-tf", str(archive)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "backup-manifest.json" in listed.stdout
    assert oct(archive.stat().st_mode & 0o777) == oct(0o600)


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(Exception, match="ValidationError"):
        parse_manifest('{"schema_version": 1, "extra": true}')


def test_restore_dry_run_does_not_write(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    code = run_restore(_args(tmp_path, dry_run=True, yes=True), site)
    assert code == 0
    assert site.restored_dump is None
    assert site.restored_media is False


def test_restore_requires_yes(tmp_path: Path, capsys) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    capsys.readouterr()
    code = run_restore(_args(tmp_path), site)
    assert code == 1
    assert "requires --yes" in capsys.readouterr().out
    assert site.restored_dump is None


def test_restore_refuses_version_mismatch(tmp_path: Path, capsys) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    site.snapshot_value = SiteSnapshot("8.0.1", "16.10", 6, 7, 2, 1)
    capsys.readouterr()
    code = run_restore(_args(tmp_path, yes=True), site)
    assert code == 1
    assert "postgres_version" in capsys.readouterr().out
    assert site.restored_dump is None


def test_restore_checks_counts_after_write(tmp_path: Path, capsys) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    site.counts = (6, 7, 2, 0)
    capsys.readouterr()
    code = run_restore(_args(tmp_path, yes=True), site)
    assert code == 1
    assert "counts 6,7,2,0 != 6,7,2,1" in capsys.readouterr().out
    assert site.restored_media is True


def test_settings_restored_only_with_dest_and_yes(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    settings = tmp_path / "settings.json"
    settings.write_text('{"x": 1}\n', encoding="utf-8")
    assert run_backup(_args(tmp_path, settings_file=str(settings)), site) == 0
    dest = tmp_path / "out" / "settings.json"
    code = run_restore(_args(tmp_path, yes=True, settings_dest=str(dest)), site)
    assert code == 0
    assert dest.read_text(encoding="utf-8") == '{"x": 1}\n'
    assert oct(dest.stat().st_mode & 0o777) == oct(0o600)


def test_check_stops_when_media_was_added(tmp_path: Path, capsys) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    (site.media / "later.png").write_bytes(b"later")
    capsys.readouterr()
    code = run_restore(_args(tmp_path, yes=True), site)
    assert code == 1
    assert "later.png" in capsys.readouterr().out
    assert site.restored_dump is None


def test_replace_skips_the_media_check(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    (site.media / "later.png").write_bytes(b"later")
    code = run_restore(_args(tmp_path, yes=True, media="replace"), site)
    assert code == 0
    assert site.restored_media is True
    assert site.merged_media is False


def test_merge_keeps_files_not_in_the_archive(tmp_path: Path) -> None:
    from xgic.cli.wagtail.site import DockerComposeSite

    media = tmp_path / "media"
    media.mkdir()
    (media / "kept.txt").write_text("kept", encoding="utf-8")
    (media / "old.txt").write_text("old", encoding="utf-8")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "old.txt").write_text("from-archive", encoding="utf-8")
    media_tar = tmp_path / "media.tar"
    subprocess.run(["tar", "-cf", str(media_tar), "-C", str(fresh), "."], check=True)
    site = DockerComposeSite(
        project_dir=tmp_path,
        compose_file=None,
        web_service="web",
        postgres_service="postgres",
        database="wagtail",
        db_user="wagtail",
        media_dir=media,
        base_url="http://127.0.0.1:8000",
    )
    site.merge_media(media_tar)
    assert (media / "kept.txt").read_text(encoding="utf-8") == "kept"
    assert (media / "old.txt").read_text(encoding="utf-8") == "from-archive"


def test_restore_media_replaces_the_directory(tmp_path: Path) -> None:
    from xgic.cli.wagtail.site import DockerComposeSite

    media = tmp_path / "media"
    media.mkdir()
    (media / "old.txt").write_text("old", encoding="utf-8")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "new.txt").write_text("new", encoding="utf-8")
    media_tar = tmp_path / "media.tar"
    subprocess.run(["tar", "-cf", str(media_tar), "-C", str(fresh), "."], check=True)
    site = DockerComposeSite(
        project_dir=tmp_path,
        compose_file=None,
        web_service="web",
        postgres_service="postgres",
        database="wagtail",
        db_user="wagtail",
        media_dir=media,
        base_url="http://127.0.0.1:8000",
    )
    site.restore_media(media_tar)
    assert not (media / "old.txt").exists()
    assert (media / "new.txt").read_text(encoding="utf-8") == "new"


def test_compose_counts_require_the_web_container(tmp_path: Path) -> None:
    from xgic.cli.wagtail.site import DockerComposeSite, SiteError

    site = DockerComposeSite(
        project_dir=tmp_path,
        compose_file=None,
        web_service="web",
        postgres_service="postgres",
        database="wagtail",
        db_user="wagtail",
        media_dir=tmp_path / "media",
        base_url="http://127.0.0.1:8000",
    )
    with pytest.raises(SiteError, match="--web-container"):
        site.current_counts()


def test_manifest_rejects_a_count_set_without_all_pages() -> None:
    from pydantic import ValidationError

    from xgic.cli.wagtail.manifest import Counts

    with pytest.raises(ValidationError):
        Counts.model_validate({"pages": 1, "images": 0, "documents": 0})


def test_backup_name_uses_project_and_utc_second(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    archives = list((tmp_path / "backups").glob("*.tar.zst"))
    assert len(archives) == 1
    assert archives[0].name.startswith("wagtail-example_")
    assert archives[0].name.endswith("_8.0.1.tar.zst")
    sidecar = archives[0].with_name(archives[0].name + ".sha256")
    assert sidecar.read_text(encoding="utf-8").endswith(f"  {archives[0].name}\n")
    manifest = LandingPair(archives[0].parent).manifest_of(archives[0])
    assert manifest.backup_id == archives[0].name.removesuffix(".tar.zst")


def test_backup_refuses_a_project_that_is_not_kebab_case(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path, project="Wagtail_Example"), site) == 1


def test_backup_refuses_an_existing_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    from xgic.cli.wagtail.commands import backup as backup_module

    class Frozen(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 10, 22, 15, 30, 45, tzinfo=UTC)

    monkeypatch.setattr(backup_module, "datetime", Frozen)
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    assert run_backup(_args(tmp_path), site) == 1


def test_restore_does_not_require_project(tmp_path: Path) -> None:
    site = FakeSite(tmp_path)
    assert run_backup(_args(tmp_path), site) == 0
    code = run_restore(_args(tmp_path, project=None, yes=True, media="replace"), site)
    assert code == 0
