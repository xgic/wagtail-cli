# XGIC Wagtail CLI

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/xgic/wagtail-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/xgic/wagtail-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/xgic-wagtail-cli.svg)](https://pypi.org/project/xgic-wagtail-cli/)
[![Python](https://img.shields.io/badge/python-3.14+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/xgic/wagtail-cli?include_prereleases)](https://github.com/xgic/wagtail-cli/releases)
[![Producer](https://img.shields.io/github/v/release/xgic/wagtail-dev?label=wagtail-dev)](https://github.com/xgic/wagtail-dev/releases)
[![GHCR image](https://img.shields.io/badge/GHCR-wagtail--dev-blue?logo=github)](https://github.com/users/xgic/packages/container/package/wagtail-dev)

**Wagtail product commands for the modular [XGIC CLI](https://github.com/xgic/cli)—ops under
`xgic wagtail …`.**

Namespace: **`xgic.cli.wagtail`** · Console group: **`xgic wagtail …`** · Brand: **XGIC CLI only**
([ADR-0005](https://github.com/xgic/ai/blob/main/docs/adr/0005-modular-xgic-cli-and-retirement-of-xde.md))

Standards hub: [xgic/ai](https://github.com/xgic/ai) ·
[README standards](https://github.com/xgic/ai/blob/main/docs/readme-standards.md) ·
Default CMS: [ADR-0006](https://github.com/xgic/ai/blob/main/docs/adr/0006-adopt-wagtail.md)

---

## Vision

Wagtail is the default CMS for new XGIC work. This module owns the **Wagtail product**
namespace under `xgic` so humans and agents share one command map. The thin site
template lives in [xgic/wagtail](https://github.com/xgic/wagtail); the Dev Container
**producer** (`ghcr.io/xgic/wagtail-dev`) lives in [xgic/wagtail-dev](https://github.com/xgic/wagtail-dev).

---

## Why this module exists

| Benefit | Detail |
|---------|--------|
| **Domain clarity** | Nested under `xgic wagtail`—no clash with core or other CMS modules |
| **Composable stack** | Depends on `xgic-cli` only |
| **Usage UX** | Missing ACTION prints **full usage**, matching top-level `xgic` |
| **AI + human parity** | Same command map in README and [AGENTS.md](AGENTS.md) |
| **Open-source rigor** | Apache-2.0, Python 3.14+, RC → TestPyPI → PyPI |

---

## Ecosystem

| Package / repo | Role |
|----------------|------|
| [xgic/cli](https://github.com/xgic/cli) | Thin core framework (`xgic`) |
| **This repo** | Wagtail product module (`xgic.cli.wagtail`) |
| [xgic/wagtail-dev](https://github.com/xgic/wagtail-dev) | Official image pins + contributor Compose |
| [xgic/wagtail](https://github.com/xgic/wagtail) | End-user site **template** |

Architecture: [ADR-0001](https://github.com/xgic/ai/blob/main/docs/adr/0001-xgic-gitlab-architecture-and-repository-naming.md)
· [ADR-0005](https://github.com/xgic/ai/blob/main/docs/adr/0005-modular-xgic-cli-and-retirement-of-xde.md)
· [ADR-0006](https://github.com/xgic/ai/blob/main/docs/adr/0006-adopt-wagtail.md).

---

## Quick start

### Development (editable)

```bash
uv pip install -e ../cli
uv pip install -e ".[dev]"
xgic wagtail
xgic wagtail info
xgic wagtail setup
xgic wagtail dev
```

`xgic wagtail` with no action prints full usage and exits `2`.
`xgic wagtail dev` waits for PostgreSQL, runs `migrate --noinput`, then
`python manage.py runserver 0.0.0.0:8000`. Requires a site from `setup`.
`xgic wagtail setup` is idempotent: config JSON, Compose `.env`, `wagtail start` when missing, Django `DATABASES` on **PostgreSQL**, and `django.contrib.postgres` in the generated `<project>/settings/base.py` `INSTALLED_APPS` (immediately before `django.contrib.admin`, for Wagtail search `SearchVectorField` / `GinIndex`). SQLite is not an XGIC default. The thin GitHub template does not vendor that settings file.

### Install (PyPI)

```bash
uv pip install "xgic-wagtail-cli>=0.1.0"
xgic wagtail --help
xgic wagtail info
xgic wagtail setup
xgic wagtail dev
```

PyPI publish follows the hub
[python-package-release.md](https://github.com/xgic/ai/blob/main/docs/python-package-release.md)
path (RC → TestPyPI → PyPI).

---

## Commands

| Command | Purpose |
|---------|---------|
| `xgic wagtail` | Full usage (missing ACTION) |
| `xgic wagtail info` | Module identity (`--json` for machine output) |
| `xgic wagtail setup [--quiet]` | First-run: config JSON, `.devcontainer/.env`, `wagtail start` if needed, PostgreSQL `DATABASES` + `django.contrib.postgres` in generated `settings/base.py` |
| `xgic wagtail schema [--output PATH]` | Write JSON Schema for `create-wagtail-config.json` (IntelliSense) |
| `xgic wagtail --help` | Same usage listing |

`dbAdapter` is **postgres** only. Dev-server helpers remain planned.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Human review in the GitHub UI before merge.
Labels required. Public-safe content only.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
