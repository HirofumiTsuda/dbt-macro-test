# Changelog

All notable changes are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/); before 1.0.0, a minor version may change the spec format.

## [0.1.0] - 2026-11-25

The first release.

### Added

- `dbt-macro-test run`: a spec in YAML under `macro_test/` is turned into throwaway models and
  dbt's native unit tests, which dbt runs; the output and the diff of a failure are dbt's own.
- Zero-config project discovery, and the project's `vars`, `dispatch`, `macro-paths` and packages
  carried over (installed packages are used as they are, otherwise `dbt deps` runs).
- Arguments are given by name and checked against the macro's declaration before dbt runs;
  `type: jinja` writes an expression, such as a `Relation`.
- `output`: a single expression (the default), `columns` (aliased or several), or `query` (a
  whole `select`).
- `expect`: rows (a list of mappings, or `format: csv` / `sql`), a `fixture` file, an `error`, and
  a `warning` together with rows.
- `overrides` of macros, `vars` and `env_vars` for a case, passed to dbt's own unit tests.
- `--select`, `--list`, `--target`, `--profiles-dir`, `--project-dir`, `--keep-generated`,
  `--verbose`; exit code 0 (passed), 1 (a case failed or errored), 2 (could not be run).
- dbt-core 1.8 and later (below 2) on Python 3.11 and later; the suite runs in CI on Linux and
  Windows, on the newest dbt-core and on 1.8. Only duckdb has been tried.

### Not yet

`ref` / `source`, text that is not SQL, DML, generic tests, dbt Fusion and adapters other than
duckdb; the README lists them with their issues.
