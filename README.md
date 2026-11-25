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

### Writing the expected rows

`expect.rows` is a list of mappings by default, one per row, and a list, a
struct or a map is written as one would in YAML. Two more ways, with `format`:

```yaml
        expect:
          format: sql          # the rows are what this query returns
          rows: "select [1, 2, 3] as l, {'a': 1, 'b': 'x'} as s, map {'k1': 1, 'k2': 2} as m"
```

```yaml
        expect:
          format: csv          # the first line names the columns
          rows: |
            id,name
            1,a
            2,b
```

A long result can live in a file instead: `fixture: numbers` takes
`macro_test/fixtures/numbers.csv` or `numbers.sql`, and the extension says
which it is (so `format` is not given with `fixture`). It is an error for the
file to be missing, or to exist in both formats. A case gives `rows` or a
`fixture`, never both.

dbt converts the expected values to the types of what the macro returns, so a
csv cell for a list or a struct is written as the warehouse writes it; a map
is `{k1=1, k2=2}` on duckdb, which is why `sql` is the easier way to write a
composite value. When a value differs, the failure shows the two, column by
column. Rows are compared in any order.

### Expecting an error

A macro that rejects its input is tested by the error it gives:

```yaml
      - name: a_negative_number_is_refused
        given:
          arguments:
            x: -5
        expect:
          error:
            message: x must not be negative      # the error's text contains this
```

The case passes when it ends in an error whose text contains the message, whether
the macro raised it (`exceptions.raise_compiler_error`) or the warehouse did (a
failed cast, for instance), and fails, saying what happened, when there was no error
or the text was different. The message is matched as a plain piece of text.

A macro that raises while dbt parses the project stops dbt for every case in the
run, unless it is guarded by `{% if execute %}`. So each case that expects an error
runs in a dbt run of its own, and the others are not affected; the cost is a dbt run
for each such case. `--verbose` and the summary count them with the rest, and dbt's own
output for them is not shown, since the error is what the case is for.

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

`output: query` is for a macro that returns a whole SELECT (it may start with a
`with`, or end with a comment). The query is the model, and `expect.rows` gives
the rows it should return: any number of rows and columns, compared by dbt in any
order. A macro that takes a relation can be handed a subquery, since the
argument is written into the SQL as it is:

```yaml
      - name: stacks_two_relations
        given:
          arguments:
            a: "(select 1 as id)"
            b: "(select 2 as id)"
        output: query
        expect:
          rows:
            - {id: 1}
            - {id: 2}
```

A relation that exists only in the project (a model, a source) needs the inputs
a unit test gives to `ref()` and `source()`, which are not supported yet.

Arguments are passed to the macro as values, so a macro that writes
`{{ b }}` into SQL writes the value as it is: `x` is a column called `x`, and
`"'x'"` is the string `'x'`.

### Overrides

A case can override what a macro reads from its surroundings, with the same
`overrides` that dbt's own unit tests have: `vars`, `env_vars`, and `macros`
(a macro called from the macro under test, or by the generated model, that
returns the given value instead). Only those three exist in dbt; asking for
anything else, `target` for instance, is an error.

A macro from a package is overridden under the name it is called by, with the
package: `spike_utils.hello`. The bare name `hello` does not match it, and
nothing says so; the case just fails because the override was not applied.

```yaml
      - name: in_ci_the_schema_gets_a_prefix       # schema_for() calls is_running_in_ci()
        given:
          arguments:
            name: analytics
        overrides:
          macros:
            is_running_in_ci: true
          vars:
            region: us
          env_vars:
            STAGE: prod
        expect:
          rows:
            - {result: "pr_analytics|us|prod"}
```

### Arguments

Arguments are given by name. Before dbt is run, they are checked against the
macro's declaration: an unknown name and a missing argument that has no default
are reported together, with the names the macro takes. An argument left out
that has a default uses the macro's own default. A macro that reads `kwargs`
accepts any extra names. Positional and `*args`-style arguments cannot be
given. Only macros defined in the project's own macro directories are checked;
a macro from a package is passed to dbt as it is.

A value that is not a plain YAML value, such as a `Relation`, is written as a
Jinja expression:

```yaml
        given:
          arguments:
            rel:
              type: jinja
              value: "{{ api.Relation.create(schema='main', identifier='orders') }}"
```

`type: literal` marks a value that must be taken literally, for a mapping that
would otherwise look like a typed argument.

If dbt cannot run a case at all (a SQL error, for instance), the SQL the tool
generated for it is printed after dbt's own output.

Then, from the project root:

```bash
dbt-macro-test run                          # everything under ./macro_test
dbt-macro-test run macro_test/safe_divide.yml
dbt-macro-test run --target ci
dbt-macro-test run --project-dir ../shop      # from anywhere; specs in ../shop/macro_test
```

To run part of the suite, give a path to a file or a directory, or select
cases with `--select`: a macro name, or `macro::case`, where `*` and `?` stand
for any characters. The option can be given more than once, and the patterns
are ORed. `--list` prints the cases that would run, as `macro::case`, without
running dbt.

```bash
dbt-macro-test run --select safe_divide             # every case of one macro
dbt-macro-test run --select "safe_*::by_zero"       # a pattern
dbt-macro-test run --list --select greeting         # only show what would run
```

The exit code is 0 when every case passed, 1 when a case failed or errored, and
2 when the tests could not be run at all: an invalid spec, a wrong argument, no
dbt project, dbt itself failing, or nothing matching `--select`. A line such
as `1 failed, 8 passed` ends the run.

The project is the nearest directory at or above the specs (or the working
directory, when no path is given) that has a `dbt_project.yml`, unless
`--project-dir` names one. Without a path, the specs are taken from
`macro_test/` in that project, so the command also works from a subdirectory.

`profiles.yml` is looked for in the order dbt itself uses: `--profiles-dir`,
then `$DBT_PROFILES_DIR`, then the project's own `profiles.yml` (where dbt would
look in the working directory), then `~/.dbt`. `--verbose` says which one was
used.

Each case becomes a throwaway model plus a native dbt unit test, generated
in a temporary directory and run by dbt itself, so the output and the diff
on failure are dbt's own. The project's `vars`, `dispatch` and `macro-paths`
are carried over; its `on-run-start` / `on-run-end` hooks are not run.

Packages: if the project has a `packages.yml` and its packages are already
installed (in `dbt_packages/`, or where `packages-install-path` says), they are
used as they are and `dbt deps` is not run, so nothing in your installed
packages is changed. Otherwise `packages.yml` is copied, with any relative
`local:` path made absolute, and `dbt deps` runs in the temporary directory.
dbt checks only that the number of installed packages matches `packages.yml`,
so a package that was added or removed without running `dbt deps` makes dbt
stop with its own message, but a package whose *version* was changed does not:
run `dbt deps` before `dbt-macro-test run`, as a CI job normally does.

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

The tests run on up to four workers (`pytest-xdist`, set in `pyproject.toml`), and the
end-to-end ones, which run dbt, take most of the time. To run one test, or to see a
failure without the workers, use `uv run pytest -n 0 path/to/test.py::test_name`.

## License

[MIT](LICENSE)
