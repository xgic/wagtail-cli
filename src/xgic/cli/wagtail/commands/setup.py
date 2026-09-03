"""``xgic wagtail setup`` — ensure Wagtail site with PostgreSQL."""

from __future__ import annotations

from xgic.cli.app import CommandContext
from xgic.cli.wagtail.project import ensure_wagtail_project


def run_setup(ctx: CommandContext) -> int:
    """Idempotent Wagtail project ensure (PostgreSQL default)."""
    quiet = bool(getattr(ctx.args, "quiet", False))
    return ensure_wagtail_project(quiet=quiet)
