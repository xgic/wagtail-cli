"""Register ``xgic.cli.wagtail`` subcommands on the core ``xgic`` CLI.

Product commands live under the ``wagtail`` group::

    xgic wagtail
    xgic wagtail info
    xgic wagtail setup
    xgic wagtail schema
    xgic wagtail dev
    xgic wagtail backup
    xgic wagtail restore
    xgic wagtail --help

Missing ACTION prints full usage (not a short argparse required-args error).
"""

from __future__ import annotations

import argparse

from xgic.cli.wagtail.commands.backup import run_backup
from xgic.cli.wagtail.commands.dev import run_dev
from xgic.cli.wagtail.commands.info import run_info
from xgic.cli.wagtail.commands.restore import run_restore
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

    dev = wagtail_sub.add_parser(
        "dev",
        help="Migrate and run the Wagtail/Django development server",
    )
    dev.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )
    dev.set_defaults(func=run_dev)

    def _add_site_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--backup-dir", required=True, help="Directory for the pair")
        parser.add_argument(
            "--base-url",
            default="http://127.0.0.1:8000",
            help="Wagtail origin for /api/v2/ listings",
        )
        parser.add_argument("--project-dir", default=None)
        parser.add_argument("--compose-file", default=None)
        parser.add_argument("--web-service", default="web")
        parser.add_argument("--postgres-service", default="postgres")
        parser.add_argument("--database", default="wagtail")
        parser.add_argument("--db-user", default="wagtail")
        parser.add_argument("--media-dir", default="media")
        parser.add_argument("--json", action="store_true")

    backup = wagtail_sub.add_parser(
        "backup",
        help="Publish a Wagtail .tar.zst pair",
    )
    _add_site_args(backup)
    backup.add_argument(
        "--settings-file",
        default=None,
        help="Optional settings file to copy into the archive. The file is not modified.",
    )
    backup.add_argument("--inventory", default="")
    backup.add_argument("--node", default="")
    backup.add_argument("--playbook", default="")
    backup.add_argument("--dry-run", action="store_true")
    backup.set_defaults(func=run_backup)

    restore = wagtail_sub.add_parser(
        "restore",
        help="Restore a Wagtail .tar.zst pair",
    )
    _add_site_args(restore)
    restore.add_argument("--archive", default=None, help="Pair to restore. Default: newest.")
    restore.add_argument("--settings-dest", default=None)
    restore.add_argument("--dry-run", action="store_true")
    restore.add_argument("--yes", action="store_true")
    restore.set_defaults(func=run_restore)
