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

### What the macro returns

By default a macro's output is treated as a single SQL expression, and its
value is the `result` column. If the macro returns columns of its own (an
aliased column, or several), say so with `output: columns` and use the aliases
as the column names in `expect.rows`:

```yaml
      - name: returns_two_columns       # {% macro two_columns(a, b) %}{{ a }} as first, {{ b }} as second{% endmacro %}
        given:
          arguments:
            a: 1
            b: "'x'"
        output: columns
        expect:
          rows:
            - {first: 1, second: x}
```

`output: query` (a macro that returns a whole SELECT) is not supported yet.

Arguments are passed to the macro as values, so a macro that writes
`{{ b }}` into SQL writes the value as it is: `x` is a column called `x`, and
`"'x'"` is the string `'x'`.

If dbt cannot run a case at all (a SQL error, for instance), the SQL the tool
generated for it is printed after dbt's own output.

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

The tool supports Python 3.11 and later (3.11 to 3.14 are tested in CI).
Development needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```
