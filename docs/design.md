# Design

How `dbt-macro-test` works, and why it is built this way. The [README](../README.md) is for using
it and the [spec reference](spec.md) lists every key of a spec; this page is for reading or
changing the code. How the design was worked out, with the evidence that the gap is real and the
prior art, is in the [design log](history/design-log.md), which is a record and not a
description.

## The idea

dbt's native unit tests run a model with given inputs and compare the rows it returns with the
rows expected. They cannot call a macro. So the tool turns each case of a spec into a throwaway
**model that calls the macro** and a **native unit test of that model**, in a temporary dbt
project, and has dbt run it. dbt does the rest: executing, comparing, printing the difference.

Everything dbt can do is left to dbt (the project's `profiles.yml`, the adapter, `vars`,
`dispatch`, packages, `overrides` of macros, `vars` and `env_vars`, the comparison of rows and the
diff on a failure). What the tool adds is the spec format, the generation of the project, a check
of the arguments before dbt runs, the cases that expect an error or a warning, and the report.

## One run

```
macro_test/*.yml
      │  load and validate                          spec/
      ▼
   cases ── check each argument against the macro's declaration     engine/signature, validate
      │
      ▼  generate a throwaway dbt project in a temporary directory   project/generate
      │
      ▼  dbt test --select test_type:unit, through dbtRunner          engine/runner
      │
      ▼  read the results, judge the cases that expect an error      engine/judge
      │  or a warning
      ▼
   PASS / FAIL lines, a summary, exit code 0, 1 or 2                cli
```

For this spec,

```yaml
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

the generated project is three files (shown as `--keep-generated` leaves them; the paths are
those of the real project):

```yaml
# dbt_project.yml: the real one, with the paths changed
name: fixture_project
profile: fixture_project
macro-paths: [/path/to/real/project/macros, /path/to/real/project/more_macros]
vars: {country: ..., region: eu}
model-paths: [models]
seed-paths: []
snapshot-paths: []
analysis-paths: []
test-paths: []
```

```sql
-- models/_mt_safe_divide_safe_divide_division_by_zero_is_null.sql
select {{ safe_divide(numerator=10, denominator=0) }} as result
```

```yaml
# models/_unit_tests.yml
unit_tests:
- name: division_by_zero_is_null
  model: _mt_safe_divide_safe_divide_division_by_zero_is_null
  given: []
  expect:
    format: dict
    rows:
    - result: null
```

- **The real project is kept except its paths.** The name (dispatch looks for macros by project
  name), the profile, `vars` and `dispatch` stay; `macro-paths` points at the real macro
  directories, so the macros are the real files and are not copied; the paths of models, seeds,
  snapshots and analyses are replaced or emptied; `on-run-start` and `on-run-end` are removed, as
  they would run at every `dbt test`.
- **The model has no inputs** (`given: []`): the macro is called inside it, with the arguments
  written as the spec gives them.
- **`output` says how the macro's text is wrapped** (`spec/output.py`): `expression` is
  `select <call> as result`, `columns` is `select <call>`, `query` is the call alone. These are
  evaluated by the warehouse. `text` is not: the model returns the macro's text as one string
  (`select '<text>' as result`, with the quotes escaped by dbt's `escape_single_quotes` and the
  blank space at both ends dropped), which dbt's unit test compares as it is.
- Packages: when the real project's are installed, they are used as they are (`packages-install-path`
  points at them) and `dbt deps` is not run; otherwise `packages.yml` is copied, with relative
  `local:` paths made absolute, and `dbt deps` runs in the temporary directory.
- Fixture files (`fixture: name`) are copied to `tests/fixtures/` of the generated project.

## Cases that run alone

Most cases run together, in one dbt run. A case that **expects an error** or **a warning** runs
in a dbt run of its own (`Case.isolated`, `split_isolated`; the project is generated under
`cases-run-alone/<n>`).

- An error: a `raise_compiler_error` in a macro that is not guarded stops dbt's parse of the whole
  project, so the other cases would never run.
- A warning: dbt reports it as an event that belongs to no case, and gives the same one more than
  once, so it can be said to be a case's only when one case runs.

The cost is a dbt run per such case. Measured on the machine it was developed on (duckdb), a run
of one case takes 3 to 4 seconds, which is mostly start-up and is the same for ten ordinary cases
run together; each further case that runs alone adds about 1.3 seconds (ten of them: 15 seconds). For
these runs dbt's own output is silenced (`--log-level none`; `--quiet` still prints errors), since
an expected error would look like a failure on the screen. The events still reach the callbacks of
`dbtRunner`, which is how the warnings are collected (`RawRun.warnings`, each once, without the
`[WARNING]: ` prefix). A case that expects an error is judged by whether the run ended in an error
that contains the text (`judge_error`); one that expects a warning also has to have its rows match
(`judge_warning`).

## Decisions

- **Wrap dbt, do not reimplement it.** Staying on dbt's native unit tests keeps the output and the
  diff dbt's own, and there is no second implementation of dbt's comparison to keep right. A spec
  says what a macro should do, which is the part worth keeping if dbt ships a way to test macros
  of its own. The first design was a pytest library that rendered macros in Python; it was dropped
  for this, and its functions were removed before the release.
- **Run dbt in the process, through `dbtRunner`**, so that the profile, the adapter and the
  project are resolved by dbt. The consequence is that the adapter must be installed in the same
  environment as the tool.
- **Arguments are by name and written as given.** A string is `"'x'"` because the text is put into
  SQL; `{type: jinja, value: ...}` is an expression, such as a `Relation`. Before dbt runs, each
  argument is checked against the macro's declaration (`engine/signature.py` reads the macros of
  the project's own directories), so a typo is a message that names the macro and the arguments it
  takes, not a dbt error about a model nobody wrote.
- **One shape of spec.** `macro`, `cases`, `given`, `output`, `expect`, `overrides`; the keys that
  dbt's own unit tests have (`overrides`, `expect` with `format`) keep their meaning. An unknown key
  is an error, so a typo is not a test that silently checks nothing.
- **Exit codes** say what happened: 0 every case passed, 1 a case failed or errored, 2 the tests
  could not be run (an invalid spec, a wrong argument, no project, dbt itself failing, nothing
  selected). A CI job can tell a broken macro from a broken setup.
- **dbt 1.8 moves into the project directory and does not go back**, and the directory of a
  generated project is deleted afterwards, so every dbt command goes through `invoke_dbt`
  (`engine/runner.py`), which puts the working directory back.

## The packages

```
src/dbt_macro_test/
  spec/      the spec: parsing, validation, the types of what a case is and expects, selection
  project/   the real project: finding it, its profiles, its packages, generating the throwaway one
  engine/    everything that talks to dbt: running it, reading what it says, judging, signatures
  cli.py     the command line, which ties the three together
```

- **Only `engine/` imports dbt**, and `spec/` and `project/` do not import `engine/`;
  `tests/test_layout.py` checks both, and that importing the package does not load dbt. The part
  that depends on dbt's internals is then one directory, and the rest can be read and tested without
  dbt.
- A package exports its public names from `__init__.py`; the root package exports nothing.
- The types follow dbt's: `Output` is an enum that owns the wrapping of the model; a case's
  expectation is `InlineRows`, `FixtureRef` or `ExpectedError` (with an `ExpectedWarning` beside
  it); what is handed to dbt as YAML is described by `TypedDict`s (`UnitTest`, `InlineExpect`,
  `FixtureExpect`, `Overrides`), so a misspelt key is a type error.

## What it relies on that dbt does not document

The tool runs dbt through `dbtRunner`, which is documented. It also uses three things that are
not, and a new dbt-core may change them:

- `dbt.config.project.load_raw_project`, to read the real `dbt_project.yml` as dbt reads it, before
  Jinja is rendered (`engine/config.py`);
- `dbt_common.clients.jinja.extract_toplevel_blocks`, to find the macros in a file and their
  arguments (`engine/signature.py`);
- the fields of the results and the events of a run (`status`, `node.model`, `message`, the level
  and the message of an event), in `engine/runner.py`.

CI runs the suite on dbt-core 1.8 and on the newest version for this reason (1.9 to 1.11 were run
once by hand).

## Limits

The README lists what is not supported, each with its issue. The ones that shape the design:

- **Every case is a unit test of a model, which runs in the warehouse.** A macro that needs a
  `ref` or a `source` to exist (#9), one that returns text that is not SQL (#29), one that runs DML
  (#30) and the return value of a macro without a database (#11) do not fit in it yet.
- **The result is compared as rows.** That is what dbt compares, and what the tool leaves to it.
- **Only duckdb has been run**, so what a macro does on another adapter, and how a csv cell for a
  composite value is read by it, has not been seen (#14).
- dbt Fusion: whether `dbtRunner` and the generated project work on it is not known; that is #23.

## Where to read more

- [`spec.md`](spec.md): every key of a spec, with examples.
- [`releasing.md`](releasing.md): how a release is made.
- [`history/design-log.md`](history/design-log.md): the evidence that the gap is real
  (dbt-labs/dbt#10547), the prior art, the kinds of macros worth testing, and the spikes on how
  dbt's unit tests behave.
