# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- Bootstrap `xgic.cli.wagtail` (`xgic wagtail` / `xgic wagtail info`).
  Missing ACTION prints full usage.
- `xgic wagtail setup` (idempotent PostgreSQL site ensure) and
  `xgic wagtail schema` (create-wagtail-config JSON Schema). SQLite is
  not an XGIC default.
