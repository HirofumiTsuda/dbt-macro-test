---
title: How to unit test dbt macros (dbt-core 1.8+)
published: false
description: dbt's native unit tests are for models, not macros. dbt-macro-test turns a few lines of YAML into one native unit test per case, and dbt runs them.
tags: dbt, dataengineering, python, testing
---

dbt's native unit tests, available from dbt-core 1.8, are written for models. Give a model its input rows and the rows you expect, and dbt compares them. A macro can't be given arguments and checked the same way. [dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547) asks for it and has been open since August 2024.

There are workarounds. One is a model that only calls the macro, with a native unit test on that model, as [this post](https://www.dumky.net/posts/unit-testing-dbt-macros-a-workaround-for-dbts-unit-testing-limitations/) describes. Another is [dbt-unittest](https://github.com/yu-iskw/dbt-unittest), whose assertion macros are run with `dbt run-operation`. dbt-utils keeps a separate [integration_tests](https://github.com/dbt-labs/dbt-utils/tree/main/integration_tests) project, and [pytest-dbt-core](https://github.com/godatadriven/pytest-dbt-core) tests macros from Python. The first one stays closest to dbt, but the test models end up in your project's manifest, and every macro needs a few files of its own.

[dbt-macro-test](https://github.com/HirofumiTsuda/dbt-macro-test) writes that first kind of test from a YAML spec. For each case it generates the throwaway model and the native unit test in a temporary project, then has dbt run them. Nothing is added to your project. Running, comparing and printing the diff are all dbt's.

## A first test

```bash
pip install dbt-duckdb        # or the adapter your project uses
pip install dbt-macro-test
```

```sql
-- macros/safe_divide.sql
{% macro safe_divide(numerator, denominator) %}
    {{ numerator }} / nullif({{ denominator }}, 0)
{% endmacro %}
```

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

```console
$ dbt-macro-test run
1 of 2 PASS _dmt_safe_divide_safe_divide_division_by_zero_is_null::division_by_zero_is_null  [PASS in 0.08s]
2 of 2 PASS _dmt_safe_divide_safe_divide_plain_division::plain_division ........ [PASS in 0.02s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=2

2 passed
```

dbt's start-up lines and the timestamps are left out above. If an expected value is wrong, dbt's own diff is printed and the exit code is 1:

```console
actual differs from expected:

@@ ,result
+++,Decimal('2.5')
---,Decimal('2.0')

1 failed, 1 passed
```

## Errors, refs and the rest

A macro that raises an error can be tested too. The message only has to be contained in the error:

```yaml
  - macro: quantity
    cases:
      - name: stops_with_an_error_when_it_is_negative
        given:
          arguments: {value: -5}
        expect:
          error:
            message: quantity must not be negative, got -5
```

A macro that calls `ref('orders')` or `source(...)` is given rows in the spec, and no real data is read. The expected rows can be written as csv, as a select or in a file. Macros of a package are named with the package, such as `dbt_utils.slugify`. A case can override `vars`, environment variables and other macros. Text that isn't SQL, such as a slug, is compared as text. A macro that inserts, merges or deletes is checked through temporary relations the tool makes for the case, and that is a real write to the target's schema, so a local or throwaway target is the one to use. [The guide](https://hirofumitsuda.github.io/dbt-macro-test/guide/) has an example for each of these, and each runs in CI.

## In CI, and what is missing

`dbt-macro-test run` exits with 0 when every case passed, 1 when one failed and 2 when the tests could not be run, for example because of an invalid spec. `--select "safe_*::by_zero"` runs part of them. The unit tests run in your warehouse, so a CI job needs the adapter, a profile, and the rights of a `dbt run` on a schema it can write to.

Only duckdb has been tried. Other adapters may work, since dbt does the running, but none has been run. The tool is at 0.2 and the spec format may still change. It needs dbt-core 1.8 or later and Python 3.11 or later, and the adapter has to be installed in the same environment because dbt runs in the same process. Whether it works on dbt Fusion is not known.

- Repository: <https://github.com/HirofumiTsuda/dbt-macro-test>
- PyPI: <https://pypi.org/project/dbt-macro-test/>
- Documentation: <https://hirofumitsuda.github.io/dbt-macro-test/>
