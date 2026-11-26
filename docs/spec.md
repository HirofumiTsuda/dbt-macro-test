# Spec reference

A spec file is YAML under `macro_test/` in the dbt project (any `*.yml` or `*.yaml`, in
directories too). This page lists every key; the [README](../README.md) has a first test and
the command line.

```yaml
macros:                       # required: a list
  - macro: safe_divide        # the macro to call; `package.macro` for a macro of a package
    cases:                    # required: at least one
      - name: plain_division  # required: letters, digits and _, unique within the macro
        given:                # optional
          arguments:          # by name; see "Arguments"
            numerator: 10
            denominator: 4
        output: expression    # optional: expression (default), columns, query or text
        overrides: {}         # optional: macros, vars and env_vars; see "Overrides"
        expect:               # required: exactly one of rows, fixture and error
          rows:
            - {result: 2.5}
          warning:            # optional, with rows or fixture: see "Expecting a warning"
            message: some text
```

An unknown key is an error that names the key and says where it is (for example
`macros[0].cases[0]: unknown key(s): bogus`); so is a wrong type. Only `overrides` lists the names
that are accepted. The exit code is 2, and nothing is run.

## Writing the expected rows

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

## Expecting an error

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

## Expecting a warning

A macro that gives a warning (`exceptions.warn(...)`) is tested for it next to what it
returns, since it still returns something:

```yaml
      - name: an_old_name_is_still_accepted_with_a_warning
        given:
          arguments:
            x: 7
        expect:
          rows:
            - {result: 7}
          warning:
            message: "careful: 7"      # a warning whose text contains this
```

The case passes when the rows match and a warning that contains the message was given
while it ran; it fails, saying why, when the rows do not match, when no warning was
given, or when the warnings that were given say something else (they are listed). `warning`
goes with `rows` or a `fixture`, not with `error`.

dbt reports a warning as an event with no case attached, so a case that expects a warning
runs in a dbt run of its own, like a case that expects an error, and the warnings it
gives are its own. The same warning, which dbt gives more than once, counts once.

## What the macro returns

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

`output: text` is for a macro that returns **text that is not SQL to run**: a plain string
such as `Hello, World!`, a slug, or the text of a statement (a `merge`, a `grant`). It is not
evaluated: the macro's text is returned as one string, in the `result` column, and compared as
text. What the statement would do is not tested, only what it says.

```yaml
      - name: makes_a_slug             # dbt_utils.slugify, which returns text, not SQL
        given:
          arguments:
            string: "Hello World!"
        output: text
        expect:
          rows:
            - {result: hello_world}
```

- A macro that takes a `Relation` or a list is given it as a `type: jinja` argument, as above;
  the text then holds what the `Relation` writes (`"main"."orders"`, with its schema).
- **Blank space at either end of the text is dropped**, the indentation of its first line
  included: it comes from how the macro's block is written, not from what the macro says. The
  inside is compared as it is, so a statement of several lines is expected with its line breaks and
  its indentation (a YAML block, `|-`, writes that well).
- A single quote in the text is escaped by dbt's own macro (`escape_single_quotes`), which each
  adapter may override; only duckdb has been tried.
- Without `output: text`, the same macro is taken for a SQL expression, and `Hello, World!` is a
  syntax error (`select Hello, World! as result`).
- **A macro that reads the `config` of the model it runs in sees the generated model's, which is
  empty.** dbt-duckdb's `get_merge_sql`, for example, validates the `merge_*` settings and stops
  with `MERGE configuration errors`; the macros that take everything as arguments work. The same
  holds for `this` and `is_incremental()`: they are those of the generated model. Setting a model's
  `config` for a case is not supported.

A relation that exists only in the project (a model, a source) needs the inputs
a unit test gives to `ref()` and `source()`, which are not supported yet.

Arguments are passed to the macro as values, so a macro that writes
`{{ b }}` into SQL writes the value as it is: `x` is a column called `x`, and
`"'x'"` is the string `'x'`.

## Overrides

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

## Arguments

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
