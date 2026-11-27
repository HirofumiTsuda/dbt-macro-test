# Writing specs: what to write for the macro you have

A spec says what a macro should give for the arguments you choose. This page goes by **the kind of
macro**: find yours in the table, copy the example, change it. Every example here is in
[`dev/sample_project`](https://github.com/HirofumiTsuda/dbt-macro-test/tree/main/dev/sample_project),
which runs in CI, so they work. [The spec reference](spec.md) lists every key.

| Your macro... | Write | Section |
|---|---|---|
| gives a value (a SQL expression) | the default | [A value](#a-value) |
| gives several columns | `output: columns` | [Columns and queries](#columns-and-whole-queries) |
| gives a whole `select` | `output: query` | [Columns and queries](#columns-and-whole-queries) |
| gives text that is not SQL (a code, a slug) | `output: text` | [Text](#text-that-is-not-sql) |
| stops with an error, or warns | `expect.error`, `expect.warning` | [Errors and warnings](#errors-and-warnings) |
| reads a `var`, an environment variable, or calls another macro | `overrides` | [Overrides](#vars-environment-variables-and-other-macros) |
| is a macro of a package | `package.macro` | [A package's macro](#a-packages-macro) |
| reads a model or a source (`ref`, `source`) | `given.inputs` | [ref and source](#a-macro-that-reads-a-model-or-a-source) |
| writes (insert, merge, delete) | `setup`, `expect.query` | [A macro that writes](#a-macro-that-writes) |
| is called by a hook and reads `this` | `{{ this }}` in `setup` and `expect.query` | [A hook's macro](#a-macro-that-a-hook-calls-and-reads-this) |
| returns the text of a statement | `run: execute` | [A statement](#a-macro-that-returns-a-statement) |
| gives something else on another database | `adapters` | [One database](#a-case-for-one-database) |

Every case has a `name`, what it is `given`, and what it should `expect`. All cases of a macro go
under it, and a spec file is a list of macros under `macros:`. Run them with `dbt-macro-test run`.

## A value

A macro that gives a SQL expression: the case says what it should be worth. The arguments go in by
name and the macro gets them **as written**: `10` is the number 10, and `Aki` is the string Aki. A macro
that puts an argument straight into the SQL (as `safe_divide` does) needs a SQL value, so a string
for it is `"'text'"`, with the quotes of SQL; a macro that quotes the text itself (a greeting, a
code) is given `Aki`. The value is the column `result` of the expected rows.

```yaml
macros:
  - macro: safe_divide
    cases:
      - name: divides
        given:
          arguments: {numerator: 10, denominator: 4}
        expect:
          rows:
            - {result: 2.5}

      - name: gives_null_when_the_denominator_is_zero
        given:
          arguments: {numerator: 10, denominator: 0}
        expect:
          rows:
            - {result: null}
```

An argument left out takes the macro's default. A value that is not plain (a column, a date, a
`Relation`) is a Jinja expression: `{type: jinja, value: "cast('2024-03-15' as date)"}`; see
[Arguments](spec.md#arguments).

**The expected rows** can be written four ways: as mappings (above), as csv, as a select, or in a
file under `macro_test/fixtures/`:

```yaml
        expect:
          format: csv            # the first line names the columns
          rows: |
            id,status
            1,open
            2,shipped
```
```yaml
        expect:
          fixture: all_orders    # macro_test/fixtures/all_orders.csv (or .sql)
```

When a case fails, dbt's own diff is shown (`+++` is what the macro gave, `---` what you expected).

## Columns and whole queries

A macro that writes columns of its own (`extract(year ...) as year, ...`): `output: columns`, and
the rows use the names the macro gives.

```yaml
  - macro: date_parts
    cases:
      - name: splits_a_date_into_year_and_month
        given:
          arguments:
            date_expression: "cast('2024-03-15' as date)"
        output: columns
        expect:
          rows:
            - {year: 2024, month: 3}
```

A macro that gives a whole `select`, in any shape: `output: query`. The relations it takes go in as
subqueries, since an argument is written into the SQL as it is.

```yaml
  - macro: all_orders
    cases:
      - name: gives_each_order_once
        given:
          arguments:
            first: "(select 1 as id, 'open' as status union all select 2, 'shipped')"
            second: "(select 2 as id, 'shipped' as status union all select 3, 'open')"
        output: query
        expect:
          rows:
            - {id: 1, status: open}
            - {id: 2, status: shipped}
            - {id: 3, status: open}
```

## Text that is not SQL

A macro that returns a code, a slug, the text of a statement: with the default, `ORD-000042` would be
read as SQL. `output: text` compares the text as it is (blank space at both ends is dropped).

```yaml
  - macro: order_code
    cases:
      - name: pads_the_number_to_six_digits
        given:
          arguments: {prefix: ORD, number: 42}
        output: text
        expect:
          rows:
            - {result: ORD-000042}
```

## Errors and warnings

A macro that stops with `raise_compiler_error`, or warns with `exceptions.warn`, is tested for what
it says. `message` is text that the error or the warning **contains**.

```yaml
  - macro: quantity
    cases:
      - name: stops_with_an_error_when_it_is_negative
        given:
          arguments: {value: -5}
        expect:
          error:
            message: quantity must not be negative, got -5

  - macro: status
    cases:
      - name: gives_the_status_and_warns_that_pending_is_going_away
        given:
          arguments: {value: pending}
        expect:
          rows:
            - {result: pending}      # the rows have to match as well
          warning:
            message: "status 'pending' is deprecated"
```

A case of either kind runs in a run of dbt of its own (about a second more each), so that an error
that stops the project does not stop the other cases, and a warning can be told from the others'.
An error that is raised while dbt parses the project, in a case that does **not** expect one, stops
the whole run (exit code 2), as it does in dbt.

## Vars, environment variables and other macros

What a macro reads from its surroundings can be set for one case:

```yaml
  - macro: greeting
    cases:
      - name: with_a_var_and_an_environment_variable_of_its_own
        given:
          arguments: {name: Aki}
        overrides:
          vars: {country: US}
          env_vars: {SHOP_NAME: web shop}
        expect:
          rows:
            - {result: "Hello, Aki! (US, web shop)"}

  - macro: price_with_tax
    cases:
      - name: with_another_rate_given_by_a_macro_override
        given:
          arguments: {amount: 100}
        overrides:
          macros: {tax_rate: 0.5}    # tax_rate() returns 0.5 in this case
        expect:
          rows:
            - {result: 150.00}
```

Without `overrides`, a case sees the `vars` and the macros of your project. See
[Overrides](spec.md#overrides).

## A package's macro

Name it with its package, and install the package as you do for the project (`dbt deps`, or let the
tool run it):

```yaml
  - macro: dbt_utils.slugify
    cases:
      - name: makes_a_slug
        given:
          arguments: {string: "'Blue Widget (Large)!'"}
        output: text
        expect:
          rows:
            - {result: blue_widget_large}
```

## A macro that reads a model or a source

A macro that calls `ref()` or `source()` needs them to exist, and the tool's project has none of
yours. Give the rows it is to see under `given.inputs`; **no real data is read**, the rows you give
are all there is.

```yaml
  - macro: orders_with_status
    cases:
      - name: counts_the_orders_that_have_the_status
        given:
          arguments: {status: "'open'"}
          inputs:
            - input: ref('orders')            # or source('shop', 'payments')
              rows:
                - {id: 1, status: open}
                - {id: 2, status: shipped}
                - {id: 3, status: open}
        expect:
          rows:
            - {result: 2}
```

(`status` goes straight into the macro's SQL, so it carries its quotes.) Instead of `rows`, an input can be a select: `sql: select 1 as id, 'open' as status`; a string with a
quote or a backslash in it has to be written that way. The rows are seen by the final `select`
only, not by a statement the macro sends by itself. See
[A macro that calls ref or source](spec.md#a-macro-that-calls-ref-or-source).

## A macro that writes

A macro that inserts, merges or deletes: the tool makes the relations of the case (from rows or a
select), as **temporary** ones, runs the macro, and compares the rows a query returns afterwards.
It drops them at the end. **This writes to the target's schema**: use a local or throwaway target
(`--target`), and read [the warning](spec.md#a-macro-that-writes).

```yaml
  - macro: remove_cancelled
    cases:
      - name: keeps_the_orders_that_are_not_cancelled
        setup:
          relations:
            orders:
              rows:
                - {id: 1, status: open}
                - {id: 2, status: cancelled}
                - {id: 3, status: shipped}
        given:
          arguments:
            orders: {type: jinja, value: relations.orders}   # the relation the tool made
        expect:
          query: select id, status from {{ relations.orders }}   # compared after the macro ran
          rows:
            - {id: 1, status: open}
            - {id: 3, status: shipped}
```

A macro that only **reads** a relation is the same without a `query`: its value is compared.

### A macro that a hook calls, and reads `this`

A `post-hook` often calls a macro that reads `this` (the full name of the table it runs for) and
writes to another table with a `merge`: a record of which tables were updated, and when. **That the
hook calls the macro is dbt's**, and is not tested here; what is tested is what the macro does.

In a case `this` is the generated model's, which is enough for that, with two things to do:

- **Its name has the id of the run in it, so it cannot be written in the rows.** `{{ this }}` is
  rendered in `setup.relations.<name>.sql` and in `expect.query`, so give a row for it there, and
  compare with it in the query.
- **Neither can a time.** Give a row an old time, and check afterwards that the time is later.

```yaml
  - macro: record_update
    cases:
      - name: records_a_table_that_is_new
        setup:
          relations:
            registry:
              sql: select 'other' as full_name, timestamp '2000-01-01' as updated_at
        given:
          arguments:
            registry: {type: jinja, value: relations.registry}
        expect:
          query: >
            select full_name = '{{ this }}' as is_this, updated_at > timestamp '2020-01-01' as is_recent
            from {{ relations.registry }} order by is_this
          rows:
            - {is_this: false, is_recent: false}   # another table is left as it was
            - {is_this: true, is_recent: true}
      - name: updates_a_table_that_is_there_and_does_not_add_it_twice
        setup:
          relations:
            registry:
              sql: select '{{ this }}' as full_name, timestamp '2000-01-01' as updated_at
        given:
          arguments:
            registry: {type: jinja, value: relations.registry}
        expect:
          query: select count(*) as n, bool_and(updated_at > timestamp '2020-01-01') as is_recent from {{ relations.registry }}
          rows:
            - {n: 1, is_recent: true}
```

The first case is the `when not matched` side of the `merge` and the second is the `when matched`
side. A macro that reads the `config` of the model, rather than `this`, sees the generated model's
too (see [the spec](spec.md#a-macro-that-writes)).

## A macro that returns a statement

A macro such as `dbt.get_merge_sql` runs nothing: it returns the text of a statement. To see what
the statement **does**, add `run: execute`: the tool runs what the macro returns, and `expect.query`
shows the rows afterwards (see the example in
[the spec reference](spec.md#a-macro-that-returns-a-statement)).

## A case for one database

The same macro can give a different value on another database: `10 / 4` is `2.5` on duckdb and `2` on
Postgres, which divides two integers as integers. Say which database a case is for with `adapters`;
on another it is skipped, and the run says so.

```yaml
  - macro: safe_divide
    cases:
      - name: integer_division_gives_a_fraction
        adapters: [duckdb]
        given:
          arguments: {numerator: 10, denominator: 4}
        expect:
          rows:
            - {result: 2.5}

      - name: integer_division_drops_the_fraction
        adapters: [postgres]
        given:
          arguments: {numerator: 10, denominator: 4}
        expect:
          rows:
            - {result: 2}
```

The database is the one of the target you run against (`--target`). See
[A case for some adapters](spec.md#a-case-for-some-adapters).

## Running some of the cases, and in CI

```bash
dbt-macro-test run                              # everything under macro_test/
dbt-macro-test run macro_test/safe_divide.yml   # one file
dbt-macro-test run --select safe_divide         # every case of one macro
dbt-macro-test run --select "safe_*::by_zero"   # macro::case; * and ? stand for any characters
dbt-macro-test run --list                       # show what would run, run nothing
dbt-macro-test run --target ci                  # a target of your profile
```

The exit code is 0 when every case passed, 1 when one failed or errored, and 2 when the tests could
not be run (an invalid spec, a wrong argument, dbt itself failing). The README has an example for
GitHub Actions.
