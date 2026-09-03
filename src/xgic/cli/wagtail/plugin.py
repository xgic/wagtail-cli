"""Register ``xgic.cli.wagtail`` subcommands on the core ``xgic`` CLI.

Product commands live under the ``wagtail`` group::

    xgic wagtail
    xgic wagtail info
    xgic wagtail setup
    xgic wagtail schema
    xgic wagtail --help

Missing ACTION prints full usage (not a short argparse required-args error).
"""

from __future__ import annotations

import argparse

from xgic.cli.wagtail.commands.info import run_info
from xgic.cli.wagtail.commands.schema import run_schema
from xgic.cli.wagtail.commands.setup import run_setup


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Entry point: ``xgic.cli.commands`` → Wagtail product commands."""
    wagtail = subparsers.add_parser(
        "wagtail",
        help="Wagtail product commands",
        description="Wagtail CMS commands for the modular XGIC CLI.",
    )
    wagtail_sub = wagtail.add_subparsers(
        dest="wagtail_command",
        help="Wagtail action",
        metavar="ACTION",
        required=False,
    )

    def _missing_action(_args: argparse.Namespace) -> int:
        wagtail.print_help()
        return 2

    wagtail.set_defaults(func=_missing_action)

    info = wagtail_sub.add_parser(
        "info",
        help="Show Wagtail CLI module version and status",
    )
    info.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    info.set_defaults(func=run_info)

    setup = wagtail_sub.add_parser(
        "setup",
        help="Ensure Wagtail site with PostgreSQL (idempotent)",
    )
    setup.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )
    setup.set_defaults(func=run_setup)

    schema = wagtail_sub.add_parser(
        "schema",
        help="Write create-wagtail-config JSON Schema (editor IntelliSense)",
    )
    schema.add_argument(
        "--output",
        metavar="PATH",
        help="Override schema output path",
    )
    schema.set_defaults(func=run_schema)
