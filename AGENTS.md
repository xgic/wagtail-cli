# AI Agent Instructions — XGIC Wagtail CLI

Public repository. Follow https://github.com/xgic/ai for multi-repo standards.

## Product

- **Package:** `xgic.cli.wagtail` (distribution `xgic-wagtail-cli`)
- **Depends on:** `xgic-cli` (thin core)
- **Architecture:** [ADR-0005](https://github.com/xgic/ai/blob/main/docs/adr/0005-modular-xgic-cli-and-retirement-of-xde.md)
- **Default CMS:** [ADR-0006](https://github.com/xgic/ai/blob/main/docs/adr/0006-adopt-wagtail.md)

## Scope

- Nested `xgic wagtail …` product commands via entry points (`xgic.cli.commands`)
- Missing ACTION prints full usage (exit 2)
- `info` reports experimental module identity
- `setup` ensures a Wagtail site on **PostgreSQL** (Compose `postgres` service); not SQLite. It patches generated `<project>/settings/base.py`: `DATABASES` plus `django.contrib.postgres` in `INSTALLED_APPS` immediately before `django.contrib.admin` (Wagtail search `SearchVectorField` / `GinIndex`; stock `wagtail start` omits it because it defaults to SQLite). Not added to the thin GitHub template.
- `schema` writes JSON Schema for `.devcontainer/create-wagtail-config.json`
- `dev` waits for PostgreSQL, runs `migrate --noinput`, then
  `manage.py runserver 0.0.0.0:8000`. Requires a site from `setup`.
- Compose lifecycle (`xgic logs` / `up` / `check`) is [xgic/dev-cli](https://github.com/xgic/dev-cli). Inside the Dev Container it uses Docker-outside-of-Docker (producer image CLI + engine socket). Do not enable Docker-in-Docker.

## Out of scope

- Private host defaults or internal inventory
- Thin CLI framework / env detection → https://github.com/xgic/cli
- Dev Container / Docker Compose lifecycle → https://github.com/xgic/dev-cli
- StreamField / site content models → consumer site repositories (https://github.com/xgic/wagtail stays an empty template)
- Site Compose / template files → https://github.com/xgic/wagtail
- Image producer → https://github.com/xgic/wagtail-dev
- Payload CMS commands → https://github.com/xgic/payload-cms-cli

## Rules

**Public GitHub writes:** Before `gh issue create|edit`, `gh pr create|edit`, or any public comment on this repository, complete the **mandatory public-safe draft gate** in https://github.com/xgic/ai/blob/main/docs/BASE-STANDARDS-FOR-ORCHESTRATED-REPOS.md (fictional placeholders only; never name private hosts, private projects, or private tracker IDs). Optional helper from the hub clone: `python scripts/public-safe-scan.py path/to/draft.md`.
- Public-safe content only
- Human UI review before merge to `main`
- Dedicated issue-number branches; Conventional Commits
- **Labels required** on issues/PRs (see community-health)
- Python 3.14+; Apache-2.0; root `CODEOWNERS` (`@xgic`)
- **No intermediate** `xgic/cli/__init__.py` that clobbers core
- **PyPI releases:** https://github.com/xgic/ai/blob/main/docs/python-package-release.md
