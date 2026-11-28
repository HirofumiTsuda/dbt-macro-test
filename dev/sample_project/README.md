# The sample project

A small dbt project of a shop, with duckdb, and a spec in `macro_test/` for each thing that
`dbt-macro-test` does. It is for reading, for trying a change by hand, and, through
`tests/test_sample.py`, for keeping the examples true: the tests of the repository run all of it.

## Run it

```bash
pip install dbt-duckdb dbt-macro-test       # in a checkout: uv run dbt-macro-test, as below
cd dev/sample_project
dbt-macro-test run                           # 35 cases: 34 run and pass, 1 is for Postgres
dbt-macro-test run --list                    # the cases, as macro::case
dbt-macro-test run --select "price_*"        # some of them
```

Nothing has to be set up: the profile is duckdb in memory. One case is for Postgres, so it is skipped
and the run says so.

**On Postgres** (what CI does): start a container, install the adapter, and point `--profiles-dir` at
`postgres/`, whose connection is in `DMT_PG_*` variables with the defaults of the container below.
The case for duckdb is skipped then, and every other one runs and passes.

```bash
docker run -d --name dmt-pg -e POSTGRES_USER=dmt -e POSTGRES_PASSWORD=dmt -e POSTGRES_DB=dmt \
  -p 5432:5432 postgres:17
pip install dbt-postgres
dbt-macro-test run --profiles-dir postgres
```
 dbt writes `target/`, `logs/` and
`.user.yml` next to it, which `.gitignore` leaves out.

## What each file shows

| Spec | Macro | It shows |
|---|---|---|
| `expressions.yml` | `cents_to_dollars`, `safe_divide` | a macro that gives a SQL expression: arguments by name, an argument with a default, the rows that are expected; and a case for each database where the result differs (`adapters`: two integers divide to `2.5` on duckdb and to `2` on Postgres) |
| `columns.yml` | `date_parts` | a macro that writes columns of its own (`output: columns`) |
| `queries.yml` | `all_orders` | a macro that gives a whole select (`output: query`), the relations handed in as subqueries |
| `text.yml` | `order_code`, `slug` | a macro that returns text that is not SQL (`output: text`) |
| `errors_and_warnings.yml` | `quantity`, `status` | an error that a macro raises (`expect.error`) and a warning it gives (`expect.warning`), which run in a run of dbt of their own |
| `overrides.yml` | `greeting`, `price_with_tax` | what a macro reads from its surroundings, set for one case: a var, an environment variable, another macro |
| `schemas.yml` | `generate_schema_name`, `is_running_in_ci` | a macro that dbt itself calls, overridden in the project: the name of a schema (`output: text`, a node that is `null`), by a var, a macro that a case gives the value of, and an environment variable. The target cannot be overridden in a case |
| `formats.yml` + `fixtures/` | `all_orders` | the expected rows as csv, as a select, and in a fixture file |
| `relations.yml` | `upsert_orders`, `record_update`, `remove_cancelled`, `archive_cancelled`, `order_total`, `order_columns`, `merge_orders_sql` | a macro that **writes** to a relation (a merge, a delete, an insert in a `statement` block, a statement the macro only returns, `run: execute`) or reads one (the value of a query, the columns through `adapter`): the tool makes the relations of the case, from rows or a select, as temporary ones, and drops them afterwards; what is compared is the rows a query returns. **These run SQL in the warehouse of the target**: see the warning in the spec reference |
| `inputs.yml` | `orders_with_status`, `paid_total` | a macro that calls `ref()` or `source()` itself: the rows it is to see are given under `given.inputs` (as `rows` or a `select`); the tool makes a stand-in for the node and reads no real data |

The macros are in `macros/`, each with a line on what it is for. `tax_rate` is the one that has no
case of its own: it is there to be overridden.

## See a failure

```bash
sed -i 's/{result: 12.50}/{result: 12.51}/' macro_test/expressions.yml
dbt-macro-test run --select cents_to_dollars    # 1 failed: dbt's own diff, and exit code 1
git checkout macro_test/expressions.yml         # put it back
```
