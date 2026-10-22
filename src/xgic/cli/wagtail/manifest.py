"""Backup manifest stored inside a Wagtail archive."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ManifestError(Exception):
    """The manifest is missing a field or contains an unknown one."""


class Member(BaseModel):
    """One file inside the archive."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Counts(BaseModel):
    """Counts from the Wagtail API v2 listing endpoints."""

    model_config = ConfigDict(extra="forbid")

    pages: int = Field(ge=0)
    images: int = Field(ge=0)
    documents: int = Field(ge=0)


class Artifacts(BaseModel):
    """Database dump, media tar, and stores left out of the archive."""

    model_config = ConfigDict(extra="forbid")

    database: Member
    media: Member
    omitted: list[str]
    settings: Member | None = None


class Control(BaseModel):
    """Who requested the backup. Empty when the caller did not set them."""

    model_config = ConfigDict(extra="forbid")

    inventory: str = ""
    node: str = ""
    playbook: str = ""


class BackupManifest(BaseModel):
    """``backup-manifest.json`` inside the archive."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    created_at: datetime
    product: Literal["wagtail"] = "wagtail"
    wagtail_version: str = Field(min_length=1)
    postgres_version: str = Field(min_length=1)
    backup_id: str = Field(min_length=1)
    payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 of database.dump, then media.tar, then settings.file "
            "when present. The sidecar is the SHA-256 of the .tar.zst."
        ),
    )
    artifacts: Artifacts
    counts: Counts
    control: Control = Field(default_factory=Control)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2) + "\n"


def parse_manifest(text: str) -> BackupManifest:
    """Load a manifest and reject unknown fields."""
    try:
        return BackupManifest.model_validate_json(text)
    except ValidationError as exc:
        raise ManifestError(f"ValidationError: {exc}") from exc


OMITTED = ("search_index", "cache")
