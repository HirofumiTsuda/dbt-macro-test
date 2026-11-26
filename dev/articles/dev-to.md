---
title: How to unit test dbt macros (dbt-core 1.8+)
published: false
description: dbt's native unit tests cover models, not macros. dbt-macro-test turns a few lines of YAML into one native unit test per case, so dbt does the running and the diff.
tags: dbt, dataengineering, python, testing
---

dbt's native unit tests, from dbt-core 1.8, test **models**: you give a model's inputs and the rows
you expect, and dbt compares them. They do not call a **macro**. So if you have a macro such as a
`safe_divide`, a slug builder or a custom `merge`, there is no built-in way to say "with these
arguments it should return this".

This is a known gap: [dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547) asks for it,
and has been open since August 2024. This post shows what people do today, and a small tool,
[dbt-macro-test](https://github.com/HirofumiTsuda/dbt-macro-test), that I wrote for it.

## Can dbt's unit tests test macros?

Not directly. A unit test is of a model. What people do instead:

| Approach | How | Where the tests live |
|---|---|---|
| A model that calls the macro, with a native unit test of it, by hand ([a write-up](https://www.dumky.net/posts/unit-testing-dbt-macros-a-workaround-for-dbts-unit-testing-limitations/)) | the macro's output is the model's, and dbt compares it | your project's `models/`, next to the real models |
| [`dbt-unittest`](https://github.com/yu-iskw/dbt-unittest) | assertion macros (`assert_equals`, ...), run with `dbt run-operation` | your project's `macros/` |
| A dedicated testing project, as dbt packages do ([`dbt-utils`](https://github.com/dbt-labs/dbt-utils/tree/main/integration_tests) has one) | seeds, models and tests of its own | a second project, kept by hand |
| [`pytest-dbt-core`](https://github.com/godatadriven/pytest-dbt-core) | a pytest plugin | Python files |

The first is the closest to dbt itself. It is also the one that puts test models in your project's
manifest, and takes three files for one macro.

## The same idea, generated

`dbt-macro-test` automates that first approach. You write a YAML spec; for each case it generates a
throwaway model that calls the macro, plus a native unit test of that model, in a temporary dbt
project, and has dbt run them. Your project is not touched, and **dbt does the running, the
comparison and the failure output**.

```bash
pip install dbt-duckdb        # or the adapter your project uses
pip install dbt-macro-test
```

A macro:

```sql
-- macros/safe_divide.sql
{% macro safe_divide(numerator, denominator) %}
    {{ numerator }} / nullif({{ denominator }}, 0)
{% endmacro %}
```

and its spec:

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

(Trimmed: dbt's start-up lines and timestamps are left out.) When a case fails you get dbt's own
diff, and the exit code is 1:

```console
actual differs from expected:

@@ ,result
+++,Decimal('2.5')
---,Decimal('2.0')

1 failed, 1 passed
```

## More than a value

The spec has a few more things, each run for real on the sample project in the repository.

**A macro that stops with an error** (the message only has to be contained in the error):

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

**A macro that reads a model or a source.** A macro that calls `ref('orders')` needs `orders` to
exist, and the generated project has none of yours. You give the rows it is to see; no real data is
read:

```yaml
        given:
          arguments: {status: "'open'"}
          inputs:
            - input: ref('orders')
              rows:
                - {id: 1, status: open}
                - {id: 2, status: shipped}
```

**A macro of a package**, by its qualified name (`dbt_utils.slugify`), **text that is not SQL**
(`output: text`), `overrides` of `vars`, environment variables and other macros for one case, and
the expected rows as csv, as a select, or in a file.

**A macro that writes** (an insert, a merge, a delete): the tool makes the relations of the case as
temporary relations, runs the macro, compares the rows a query returns afterwards, and drops them.
This one is a real write to your target's schema, so use a local or throwaway target.

[The guide](https://hirofumitsuda.github.io/dbt-macro-test/guide/) goes by the kind of macro, with an
example for each; every one runs in CI.

## In CI

One command, and exit codes: 0 when every case passed, 1 when one failed, 2 when the tests could not
be run (an invalid spec, a wrong argument name, dbt itself failing). `--select "safe_*::by_zero"`
runs some of the cases. It needs what `dbt test` needs: the adapter and a profile. Unit tests run in
your warehouse, so a CI job needs the rights of a `dbt run` on a schema it can write to.

## What it does not do

I would rather say it than have you find out:

- **Only duckdb has been run.** The tool leaves the work to dbt, so other adapters may well work,
  but none has been tried.
- It is **alpha** (0.2), and the spec format may still change. dbt-core 1.8 or later, Python 3.11 or
  later; it runs dbt in the same process, so the adapter has to be installed next to it.
- Whether it works on dbt Fusion is not known (it runs dbt-core in the process), and it cannot assert
  on a macro's return value without a warehouse connection.

## Links

- Repository: <https://github.com/HirofumiTsuda/dbt-macro-test>
- PyPI: <https://pypi.org/project/dbt-macro-test/>
- Documentation: <https://hirofumitsuda.github.io/dbt-macro-test/>

If you test macros some other way, or have a macro this cannot express, I would like to hear it:
an issue on the repository is the best place.
