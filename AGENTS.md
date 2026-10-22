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
- `backup` publishes one `.tar.zst` and `.sha256`. The manifest stays inside
  the archive. The name is `{project}_{YYYYMMDD}T{HHMMSS}Z_{version}.tar.zst`
  (example `wagtail-example_20261022T153045Z_8.0.1.tar.zst`). `--project` is
  required and must be kebab-case. `restore` opens `--archive` and does not
  take `--project`. `restore` checks that pair before it writes and requires `--yes`.
  `--media` defaults to `check`: added or newer media files stop the restore
  and are listed. `replace` swaps the media directory. `merge` keeps files
  that are not in the archive.
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
- **Labels (mandatory):** Every issue and pull request gets exactly one type label in the create call: `bug`, `enhancement`, `documentation`, `standards`, or `chore`. Welcome Discussion posts use `welcome` and `documentation`. Do not put scoped GitLab labels on GitHub. https://github.com/xgic/ai/blob/main/docs/community-health.md#labels-required
- Python 3.14+; Apache-2.0; root `CODEOWNERS` (`@xgic`)
- **No intermediate** `xgic/cli/__init__.py` that clobbers core
- **PyPI releases:** https://github.com/xgic/ai/blob/main/docs/python-package-release.md
- **Release milestone:** titled `X.Y.Z`, matching the published version. The Git tag stays `vX.Y.Z`. Set it on every issue and pull request included in the release. GitHub does not copy the issue milestone onto the pull request. The candidate and the final publish share it. When the shipped version changes, move both to that `X.Y.Z` before the milestone closes. Close the parent issue, then the milestone, after the final publish and its acceptance. https://github.com/xgic/ai/blob/main/docs/work-tracking-and-checklists.md
