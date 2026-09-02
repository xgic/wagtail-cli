# XGIC Wagtail CLI

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![CI](https://github.com/xgic/wagtail-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/xgic/wagtail-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14+-blue?logo=python&logoColor=white)](https://www.python.org/)

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
```

`xgic wagtail` with no action prints full usage and exits `2`.

### Install (PyPI)

PyPI publish follows the hub
[python-package-release.md](https://github.com/xgic/ai/blob/main/docs/python-package-release.md)
path (RC → TestPyPI → PyPI). Until the first release is published, install from a clone:

```bash
uv pip install "git+https://github.com/xgic/cli.git@main"
uv pip install "git+https://github.com/xgic/wagtail-cli.git@main"
```

---

## Commands

| Command | Purpose |
|---------|---------|
| `xgic wagtail` | Full usage (missing ACTION) |
| `xgic wagtail info` | Module identity (`--json` for machine output) |
| `xgic wagtail --help` | Same usage listing |

Project ensure/create and dev-server helpers are planned; they are not in 0.1.0.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Human review in the GitHub UI before merge.
Labels required. Public-safe content only.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
