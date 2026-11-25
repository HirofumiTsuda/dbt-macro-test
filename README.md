# dbt-macro-test

[![CI](https://github.com/HirofumiTsuda/dbt-macro-test/actions/workflows/ci.yml/badge.svg)](https://github.com/HirofumiTsuda/dbt-macro-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![dbt-core 1.8+](https://img.shields.io/badge/dbt--core-1.8%2B-orange.svg)

Unit tests for dbt macros. You write what a macro should return for given arguments, in YAML;
the tool runs it through dbt's own unit tests.

```yaml
# macro_test/safe_divide.yml
macros:
  - macro: safe_divide
    cases:
      - name: division_by_zero_is_null
        given:
          arguments: {numerator: 10, denominator: 0}
        expect:
          rows:
            - {result: null}
```

**Status: not released yet.** The interface may still change, and it is not on PyPI. It has
been tried on duckdb only (see [What is not supported](#what-is-not-supported)).

This project is independent and is not affiliated with or endorsed by dbt Labs. "dbt" is a
trademark of dbt Labs, Inc.

## Why

dbt's native unit tests (1.8+) cover models only; there is no way to call a macro with given
inputs and assert on what it produces
([dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547)). This tool turns each case
of a spec into a throwaway model and a native dbt unit test in a temporary directory, and has dbt
run it. Execution, comparison, and the output when a case fails are dbt's own, not a second
implementation; what the tool adds is the spec format, the generation, and reading the result
back. If dbt ships macro unit tests of its own, the specs say what a macro should do and are
the part worth keeping; see [`docs/design.md`](docs/design.md) for the design, the evidence for
the gap and the prior art.

## Install

The tool runs dbt **in the same process**, so the adapter of your project has to be installed in
the same environment, with dbt-core (1.8 or later; the tool brings it):

```bash
pip install dbt-duckdb        # or dbt-snowflake, dbt-bigquery, ... the one your project uses
pip install "dbt-macro-test @ git+https://github.com/HirofumiTsuda/dbt-macro-test"
```

It is not on PyPI yet, hence the second line. Python 3.11 or later; Linux and Windows are run
in CI, macOS has not been.

## A first test

In a dbt project, with a macro:

```sql
-- macros/safe_divide.sql
{% macro safe_divide(numerator, denominator) %}
    {{ numerator }} / nullif({{ denominator }}, 0)
{% endmacro %}
```

write a spec under `macro_test/`:

```yaml
# macro_test/safe_divide.yml
macros:
  - macro: safe_divide
    cases:
      - name: plain_division
        given:
          arguments: {numerator: 10, denominator: 4}
        expect:
          rows:
            - {result: 2.5}      # a macro's output is the `result` column
      - name: division_by_zero_is_null
        given:
          arguments: {numerator: 10, denominator: 0}
        expect:
          rows:
            - {result: null}
```

and run it from the project:

```console
$ dbt-macro-test run
1 of 2 PASS _mt_safe_divide_safe_divide_division_by_zero_is_null::division_by_zero_is_null  [PASS in 0.08s]
2 of 2 PASS _mt_safe_divide_safe_divide_plain_division::plain_division ......... [PASS in 0.02s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=2

2 passed
```

When a case fails, dbt's own diff is shown, and the exit code is 1 (here the spec expected `2.0`):

```console
[ERROR]: in unit_test plain_division (models/_unit_tests.yml)

actual differs from expected:

@@ ,result
+++,Decimal('2.5')
---,Decimal('2.0')

1 failed, 1 passed
```

Both outputs are trimmed (dbt's start-up lines and the timestamps are left out). They are from
running exactly this, in a new project with a duckdb profile and the tool installed as above.

## What a spec can say

Arguments are given by name. A case can expect rows (written out, as csv or SQL, or in a file),
an error, or a warning; it can return a whole `select`, several columns, or a value of a
composite type; and it can override macros, `vars` and environment variables for that case. All
of it is in the [spec reference](docs/spec.md).

## The command line

```bash
dbt-macro-test run                              # everything under ./macro_test
dbt-macro-test run macro_test/safe_divide.yml   # one file, or a directory
dbt-macro-test run --target ci                  # a target of the profile
dbt-macro-test run --project-dir ../shop        # from anywhere
dbt-macro-test run --select safe_divide         # every case of one macro
dbt-macro-test run --select "safe_*::by_zero"   # macro::case; * and ? stand for any characters
dbt-macro-test run --list --select greeting     # show what would run, run nothing
```

| Option | |
|---|---|
| `PATH` | A spec file or a directory. Default: `macro_test/` of the project. |
| `--project-dir` | The dbt project. Default: the nearest directory at or above `PATH` (or the working directory) with a `dbt_project.yml`. |
| `--profiles-dir` | Where `profiles.yml` is. Default: `$DBT_PROFILES_DIR`, then the project's own `profiles.yml`, then `~/.dbt` (the order dbt uses). |
| `--target` | The target of the profile. |
| `--select` | Run only the cases that match; can be given more than once, the patterns are ORed. |
| `--list` | Print the cases that would run, as `macro::case`, and stop. |
| `--keep-generated` | Keep the generated dbt project (a temporary directory) and print where it is. |
| `--verbose` | Say what is carried over from the project, and which `profiles.yml` was used. |

The exit code is **0** when every case passed, **1** when a case failed or errored, and **2** when
the tests could not be run at all: an invalid spec, a wrong argument, no dbt project, dbt itself
failing, or nothing matching `--select`. The last line says what happened, such as
`1 failed, 8 passed`.

## What is carried over from the project

The project's `vars`, `dispatch` and `macro-paths` are carried over, so a macro sees what it
sees in the real project, and its packages (`packages.yml`) are available to it. Its
`on-run-start` and `on-run-end` hooks are not run. If a case cannot be run at all (a SQL error,
for instance), the SQL generated for it is printed after dbt's own output.

Packages that are already installed (in `dbt_packages/`, or where `packages-install-path`
says) are used as they are and `dbt deps` is not run, so nothing in them is changed. Otherwise
`packages.yml` is copied (a relative `local:` path made absolute) and `dbt deps` runs in the
temporary directory.

## Using it in CI

The tool needs what `dbt test` needs: the adapter installed, a `profiles.yml`, and a connection
to the warehouse in it. **Unit tests run against the warehouse**: dbt's unit-test
materialization creates a temporary relation for each case, to read the types of the columns, and
drops it (`unit.sql` in dbt-core's global project, which an adapter may override; dbt-duckdb does
not). What exactly is sent is the adapter's `create_table_as`, and only duckdb's has been seen
(`create temporary table`, in dbt's log), so plan for the credentials to need the rights of a
`dbt run` on a schema you can write to.

```yaml
# .github/workflows/macro-test.yml
name: macro tests
on: [pull_request]

jobs:
  macro-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install dbt-duckdb "dbt-macro-test @ git+https://github.com/HirofumiTsuda/dbt-macro-test"
      - run: dbt deps            # leave this out if the project has no packages.yml
      - run: dbt-macro-test run
        env:
          DBT_PROFILES_DIR: ci   # the directory of a profiles.yml that CI can use
```

- **`profiles.yml`**: give it with `--profiles-dir` or `DBT_PROFILES_DIR`. Keep the credentials
  out of it and read them from the environment with `{{ env_var('SNOWFLAKE_PASSWORD') }}`, and
  set them from the secrets of the repository.
- **Secrets are not available to pull requests from forks**, so a job that needs the warehouse
  does not work for them. Two ways round it: run the macro tests only for branches of the
  repository (`on: push`, or `if: github.event.pull_request.head.repo.full_name ==
  github.repository` on the job), or use a local adapter for CI, as follows.
- **A local adapter, such as duckdb, as the CI target** needs no credentials and no warehouse
  (add a `ci` target of type `duckdb` to `profiles.yml`, and `--target ci`). The price: dbt picks
  the implementation of a macro by the type of the adapter (`adapter.dispatch`), so a run on duckdb
  tests the `duckdb__` or `default__` implementation, not the one for your warehouse, and SQL
  that only your warehouse understands will not run on it. It is a good fit for macros that
  are plain SQL or Jinja, and not for what is warehouse-specific.
- **`dbt deps`**: it needs the network (the hub, or git), and it is the slowest step of a typical
  job; cache `dbt_packages/` on a hash of `packages.yml` (or `package-lock.yml`) if it matters.
  When `dbt_packages/` is there, the tool uses it as it is and does not run `dbt deps`. dbt
  checks only that the *number* of installed packages matches `packages.yml`, so a package whose
  *version* was changed is not noticed: run `dbt deps` before `dbt-macro-test run`, as the example
  does.

## What is not supported

Each of these has an issue.

- A macro that needs a `ref` or a `source` to exist, such as `dbt_utils.star` or
  `union_relations` ([#9](https://github.com/HirofumiTsuda/dbt-macro-test/issues/9)).
- A macro that returns text which is not SQL, such as `dbt_utils.slugify`
  ([#29](https://github.com/HirofumiTsuda/dbt-macro-test/issues/29)); and asserting on a
  macro's return value without a database
  ([#11](https://github.com/HirofumiTsuda/dbt-macro-test/issues/11)).
- A macro that runs DML, such as `merge`
  ([#30](https://github.com/HirofumiTsuda/dbt-macro-test/issues/30)).
- Generic tests ([#13](https://github.com/HirofumiTsuda/dbt-macro-test/issues/13)), and asserting on
  which macros were called ([#16](https://github.com/HirofumiTsuda/dbt-macro-test/issues/16)).
- dbt Fusion ([#23](https://github.com/HirofumiTsuda/dbt-macro-test/issues/23)); the tool runs
  dbt-core in-process.
- Adapters other than duckdb: the tool leaves the work to dbt, so others may well work, but
  none has been run ([#14](https://github.com/HirofumiTsuda/dbt-macro-test/issues/14)).

The tool reaches into dbt-core's own modules (`dbtRunner`, the manifest, the macro generator),
which are not a documented interface; the suite is run on dbt-core 1.8 and on the newest one in
CI to find where they differ.

## Development

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```

The tests run on up to four workers (`pytest-xdist`, set in `pyproject.toml`), and the
end-to-end ones, which run dbt, take most of the time. To run one test, or to see a
failure without the workers, use `uv run pytest -n 0 path/to/test.py::test_name`. CI runs the
suite on Python 3.11 to 3.14, on dbt-core 1.8, and on Windows; dbt-core 1.9, 1.10 and 1.11 were
each run once by hand.

## License

[MIT](LICENSE)
