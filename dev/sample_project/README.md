# The sample project

A small dbt project of a shop, with duckdb, and a spec in `macro_test/` for each thing that
`dbt-macro-test` does. It is for reading, for trying a change by hand, and, through
`tests/test_sample.py`, for keeping the examples true: the tests of the repository run all of it.

## Run it

```bash
pip install dbt-duckdb dbt-macro-test       # in a checkout: uv run dbt-macro-test, as below
cd dev/sample_project
dbt-macro-test run                           # 18 cases, all of them pass
dbt-macro-test run --list                    # the cases, as macro::case
dbt-macro-test run --select "price_*"        # some of them
```

Nothing has to be set up: the profile is duckdb in memory. dbt writes `target/`, `logs/` and
`.user.yml` next to it, which `.gitignore` leaves out.

## What each file shows

| Spec | Macro | It shows |
|---|---|---|
| `expressions.yml` | `cents_to_dollars`, `safe_divide` | a macro that gives a SQL expression: arguments by name, an argument with a default, the rows that are expected |
| `columns.yml` | `date_parts` | a macro that writes columns of its own (`output: columns`) |
| `queries.yml` | `all_orders` | a macro that gives a whole select (`output: query`), the relations handed in as subqueries |
| `text.yml` | `order_code`, `slug` | a macro that returns text that is not SQL (`output: text`) |
| `errors_and_warnings.yml` | `quantity`, `status` | an error that a macro raises (`expect.error`) and a warning it gives (`expect.warning`), which run in a run of dbt of their own |
| `overrides.yml` | `greeting`, `price_with_tax` | what a macro reads from its surroundings, set for one case: a var, an environment variable, another macro |
| `formats.yml` + `fixtures/` | `all_orders` | the expected rows as csv, as a select, and in a fixture file |

The macros are in `macros/`, each with a line on what it is for. `tax_rate` is the one that has no
case of its own: it is there to be overridden.

## See a failure

```bash
sed -i 's/{result: 12.50}/{result: 12.51}/' macro_test/expressions.yml
dbt-macro-test run --select cents_to_dollars    # 1 failed: dbt's own diff, and exit code 1
git checkout macro_test/expressions.yml         # put it back
```
