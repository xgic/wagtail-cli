"""``xgic wagtail info`` — module status."""

from __future__ import annotations

import argparse
import json

from xgic.cli.utils.output import print_info, print_success
from xgic.cli.wagtail import __version__


def run_info(args: argparse.Namespace) -> int:
    """Print Wagtail CLI module identity and capabilities."""
    payload = {
        "module": "xgic.cli.wagtail",
        "package": "xgic-wagtail-cli",
        "version": __version__,
        "status": "experimental",
        "commands": ["info", "setup", "schema"],
        "planned": [
            "dev server helpers",
        ],
        "repository": "https://github.com/xgic/wagtail-cli",
        "template": "https://github.com/xgic/wagtail",
        "producer": "https://github.com/xgic/wagtail-dev",
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
        return 0

    print_success(f"XGIC Wagtail CLI {__version__} (experimental)")
    print_info("Namespace: xgic.cli.wagtail")
    print_info("Repo: https://github.com/xgic/wagtail-cli")
    print_info("Commands: info, setup, schema")
    print_info("Template: https://github.com/xgic/wagtail")
    return 0
