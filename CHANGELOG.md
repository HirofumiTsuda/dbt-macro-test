# Changelog

All notable changes are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/); before 1.0.0, a minor version may change the spec format.

## [Unreleased]

<!-- Each version starts, under its heading and before the first ###, with a paragraph that says
     what it is for. It is the head of the GitHub release, which the release workflow makes from
     this entry (.github/scripts/release_notes.py), and a release without it does not get built. -->

### Added

- `temporary: false` on a relation of `setup.relations`: the relation is made with dbt's
  `create_table_as(false, ...)` instead of as a temporary one, for an adapter whose temporary
  relation is not what the case needs (on Spark and Databricks it is a view, which a macro cannot
  write to). The kind of table is the adapter's to say; the database and the schema of the target
  have to exist. Tried on duckdb and Postgres, and by hand on Spark (an `INSERT` and a `MERGE`, on Delta). #127.

### Fixed

- The relations of a case that are not temporary are dropped on Spark: the tool dropped them with
  `get_drop_sql`, whose `cascade` Spark refuses, and now with dbt's `drop_relation`, which the
  adapter overrides. Still the same on duckdb and Postgres. #128.

## [0.3.0] - 2026-11-27

Run on Postgres, and write a case for each database where a macro gives a different result. The
sample project and the project of the tests run on Postgres in CI, a case can be limited to some
adapters with `adapters`, and the drop of the relations of a case no longer fails on Postgres.

### Changed

- The sample project runs on Postgres as well as duckdb (a CI job runs it against a Postgres
  container), with a case for each database where the result differs: two integers divide to `2.5`
  on duckdb and to `2` on Postgres. `cents_to_dollars` of the sample divides by `100.0`, so that it
  gives the same on both.

### Added

- `adapters` on a case: `adapters: [duckdb]` limits a case to some adapters (the `type` of the target
  the run uses). On another it is skipped and said so (`SKIP ...`, and `N skipped` in the summary),
  which is not a failure. For a macro whose result depends on the database, such as `10 / 4`, which
  is `2.5` on duckdb and `2` on Postgres. Part of #88 (tags are not done).

### Fixed

- On Postgres, the drop of the relations that a case made failed (`Tried to commit transaction ...,
  but it does not have one open!`) and the tool said that they might be left in the warehouse, which
  they were not (a temporary table goes with its connection). The drop now runs in a transaction, as
  dbt's `get_drop_sql` statement, so that the commit has something to commit. Found by running the
  sample on Postgres (#116).

## [0.2.0] - 2026-11-26

Test more kinds of dbt macros: ones that read a model (`ref`, `source`), ones that write to tables,
and ones that return text or a statement. The models the tool generates are named `_dmt_…` now.

### Changed

- The models that the tool generates are named `_dmt_<spec>_<macro>_<case>` (for *dbt macro test*),
  where 0.1.0 named them `_mt_<spec>_<macro>_<case>`. Not an interface, but dbt prints the names in
  the output of a run, so they are seen. (The relations that a case makes, and the macro that drops
  them, are new in this release and have `_dmt_` from the start.)

- The `Documentation` link of the package is the documentation site, not the spec reference on
  GitHub.

### Added

- A documentation site, <https://hirofumitsuda.github.io/dbt-macro-test/>: a guide of what to write
  for each kind of macro (every example in it runs in CI), the spec reference, the design and the
  changelog. The README has a table of the same kinds that points to it.

- `run: execute`: a macro that returns the text of a statement, such as `dbt.get_merge_sql`, has that
  statement run by the tool (`run_query`), and `expect.query` shows what it did to the relations of
  the case. Without it the text is dropped, as before. Only duckdb has been tried.

- `given.inputs`: a macro that calls `ref()` or `source()` itself (`dbt_utils.star` on a model,
  `basic_aggregation` over rows) is given the rows it is to see, as `rows` or a `select`. The tool
  writes a stand-in for each node, which is never built, and hands the rows to dbt as a select,
  since for rows written as mappings dbt asks the warehouse for the columns of the upstream
  relation. No real data is read. A string with a quote, a backslash or Jinja is written with
  `sql`. A `ref` that no case gives is said to belong under `given.inputs`. The rows are seen by the
  final `select` only, not by a statement the macro runs by itself (`run_query`). Only duckdb has been
  tried.

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

The first release. Test a dbt macro like a function: call it with the arguments you choose, say what it
should return in a few lines of YAML, and run it on your machine or in CI, as dbt's own unit tests.

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
