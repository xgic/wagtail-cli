"""``xgic wagtail schema`` — write create-wagtail-config JSON Schema."""

from __future__ import annotations

from pathlib import Path

from xgic.cli.app import CommandContext
from xgic.cli.utils.output import print_success, print_warning
from xgic.cli.wagtail.config import DEFAULT_SCHEMA_FILE
from xgic.cli.wagtail.schema import write_schema


def run_schema(ctx: CommandContext) -> int:
    """Write JSON Schema for create-wagtail-config.json."""
    override = getattr(ctx.args, "output", None)
    path = Path(override) if override else DEFAULT_SCHEMA_FILE
    try:
        written = write_schema(path)
    except OSError as exc:
        print_warning(f"Could not write {path}: {exc}")
        return 1
    print_success(f"Wrote {written} (IntelliSense for create-wagtail-config.json)")
    return 0
