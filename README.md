# dbt-macro-test

Unit tests for dbt macros.

dbt's native unit tests (1.8+) cover models only; there is no way to call a
macro with given inputs and assert on what it produces
([dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547)). This
project aims to fill that gap by turning small YAML specs into dbt's own unit
tests, so execution, comparison and failure output stay identical to
official behavior.

**Status: early design / prototyping.** Nothing is released and the interface
is not stable. See [`docs/design.md`](docs/design.md) for the design, the
evidence for the gap, prior art, and the spike results so far.

This project is independent and is not affiliated with or endorsed by dbt
Labs. "dbt" is a trademark of dbt Labs, Inc.

## Usage

Put specs under `macro_test/` in your dbt project. Each case calls a macro with
named arguments and states the rows it should produce (the macro's output is
the `result` column):

```yaml
# macro_test/safe_divide.yml
macros:
  - macro: safe_divide
    cases:
      - name: division_by_zero_is_null
        given:
          arguments:
            numerator: 10
            denominator: 0
        expect:
          rows:
            - {result: null}
```

Then, from the project root:

```bash
dbt-macro-test run                          # everything under ./macro_test
dbt-macro-test run macro_test/safe_divide.yml
dbt-macro-test run --target ci
```

Each case becomes a throwaway model plus a native dbt unit test, generated
under `target/macro_test/` and run by dbt itself, so the output and the diff
on failure are dbt's own. The project's `vars`, `dispatch` and `macro-paths`
are carried over; its `on-run-start` / `on-run-end` hooks are not run.

Not on PyPI yet. To try it from a checkout of this repository, run this from
the root of your dbt project:

```bash
uv run --project <path to this checkout> dbt-macro-test run
```

## Development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```
