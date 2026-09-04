"""``xgic wagtail dev`` — foreground Django/Wagtail runserver."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from xgic.cli.app import CommandContext
from xgic.cli.utils.output import print_info, print_warning
from xgic.cli.wagtail.project import is_wagtail_project_complete

_SIGINT_EXIT_CODES = {130, -signal.SIGINT, 128 + signal.SIGINT}


def _wait_for_postgres(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), 2.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _manage_py(root: Path) -> Path:
    return root / "manage.py"


def run_dev(ctx: CommandContext) -> int:
    """Migrate (idempotent) and run ``manage.py runserver 0.0.0.0:8000``."""
    quiet = bool(getattr(ctx.args, "quiet", False))
    root = Path.cwd()
    if not is_wagtail_project_complete(root):
        print_warning(
            "No Wagtail site in this workspace. Run: xgic wagtail setup"
        )
        return 2

    manage = _manage_py(root)
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    if not _wait_for_postgres(host, port):
        print_warning(
            f"PostgreSQL is not reachable at {host}:{port}. "
            "Start Compose postgres, then retry: xgic wagtail dev"
        )
        return 1

    python = sys.executable
    if not quiet:
        print_info("Running: python manage.py migrate --noinput")
    migrate = subprocess.run(
        [python, str(manage), "migrate", "--noinput"],
        cwd=str(root),
        check=False,
    )
    if migrate.returncode != 0:
        print_warning("migrate failed. Fix the database, then retry: xgic wagtail dev")
        return int(migrate.returncode)

    bind = os.environ.get("WAGTAIL_DEV_BIND", "0.0.0.0:8000")
    if not quiet:
        print_info(f"Launching: python manage.py runserver {bind}")
        print_info("Stop with Ctrl+C.")

    try:
        proc = subprocess.Popen(
            [python, str(manage), "runserver", bind],
            cwd=str(root),
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except OSError as exc:
        print_warning(f"Could not start runserver: {exc}")
        return 1

    try:
        returncode = int(proc.wait())
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        try:
            returncode = int(proc.wait(timeout=15))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            returncode = 130

    if returncode in _SIGINT_EXIT_CODES:
        if not quiet:
            print_info("Development server stopped by user (Ctrl+C).")
        return 0
    return returncode
