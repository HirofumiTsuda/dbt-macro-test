# Changelog

All notable changes are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/); before 1.0.0, a minor version may change the spec format.

## [Unreleased]

### Changed

- The models that the tool generates are named `_dmt_<spec>_<macro>_<case>` (for *dbt macro test*),
  where 0.1.0 named them `_mt_<spec>_<macro>_<case>`. Not an interface, but dbt prints the names in
  the output of a run, so they are seen. (The relations that a case makes, and the macro that drops
  them, are new in this release and have `_dmt_` from the start.)

### Added

- `output: text`: a macro that returns text that is not SQL (a slug such as `dbt_utils.slugify`,
  the text of a `merge`) is compared as text. The text is returned as one string, with a single
  quote escaped by dbt's own macro and the blank space at both ends dropped. Only duckdb has been
  tried.

- `setup.relations` and `expect.query`: a macro that runs statements itself (an upsert, a delete), or
  that reads a relation, is tested with relations that the tool makes for the case (from `rows` or a
  `select`) and by the rows a query returns afterwards. The tool makes them as temporary relations
  with dbt's own `make_temp_relation` and `create_table_as`, so it has no code for any adapter, and
  drops them after the tests (dbt's `drop_relation_if_exists`, by a `run-operation`), which matters
  on adapters whose temporary relation is not dropped with the connection. **A real write, with
  nothing that asks first**: the spec reference says so, and what "temporary" is on each adapter.
  Only duckdb has been tried.

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
