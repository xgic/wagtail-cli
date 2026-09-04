# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## Unreleased

## [0.1.0] - 2026-09-04

### Added

- First PyPI release. Depends on `xgic-cli>=0.2.1`.
- `xgic wagtail dev`: wait for PostgreSQL, `migrate --noinput`, then
  `manage.py runserver 0.0.0.0:8000`. Requires `xgic wagtail setup` first.
- Bootstrap `xgic.cli.wagtail` (`xgic wagtail` / `xgic wagtail info`).
  Missing ACTION prints full usage.
- `xgic wagtail setup` (idempotent PostgreSQL site ensure) and
  `xgic wagtail schema` (create-wagtail-config JSON Schema). SQLite is
  not an XGIC default.

### Fixed

- setup inserts `django.contrib.postgres` into the generated
  `<project>/settings/base.py` `INSTALLED_APPS` (immediately before
  `django.contrib.admin`) so Wagtail search (`SearchVectorField` /
  `GinIndex`) can migrate on PostgreSQL (`postgres.E005`). Not added
  to the thin GitHub template.

## [0.1.0rc1] - 2026-09-04

### Added

- First TestPyPI release candidate for 0.1.0.
