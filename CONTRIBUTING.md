# Contributing to XGIC Wagtail CLI

Thank you for contributing.

## Standards

- Multi-repo policy: https://github.com/xgic/ai
- Community health (labels required): https://github.com/xgic/ai/blob/main/docs/community-health.md
- Architecture: [ADR-0005](https://github.com/xgic/ai/blob/main/docs/adr/0005-modular-xgic-cli-and-retirement-of-xde.md)
- Default CMS: [ADR-0006](https://github.com/xgic/ai/blob/main/docs/adr/0006-adopt-wagtail.md)
- Core CLI: https://github.com/xgic/cli

## Workflow

1. Open an issue (use the templates; **labels required**).
2. Branch from `main` with the issue number in the name.
3. Use detailed Conventional Commits.
4. Open a PR to `main` with appropriate **labels** (`enhancement`, `bug`, `documentation`, `standards`, `chore`, …).
5. Human review and approval in the GitHub UI before merge.

## Development

This repository is a **pure Python CLI module**. Prefer **`uv`** for local
development ([BASE-STANDARDS](https://github.com/xgic/ai/blob/main/docs/BASE-STANDARDS-FOR-ORCHESTRATED-REPOS.md)
dual-mode Python environments). Open **this repository folder** as the VS Code
workspace so a parent multi-folder workspace does not auto-activate the wrong
`.venv`.

```bash
uv pip install -e ../cli
uv pip install -e ".[dev]"
uv run pytest
uv run ruff check src tests
```

PyPI publish uses `uv` for build and clean-env smoke
([python-package-release.md](https://github.com/xgic/ai/blob/main/docs/python-package-release.md)).
Do not use `uv publish` for official releases.

## Public safety

Do not include private infrastructure details, private tracker IDs, or internal paths in issues, PRs, or code.
