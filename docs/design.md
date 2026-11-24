# dbt-macro-test: design sketch

Status: **implementation started**, 2026-09-17. A `uv`-managed Python package
exists at the repo root (`src/dbt_macro_test/`) with a passing pytest suite
covering all three primitives described below. This file is being kept up to
date as the design evolves, not as a frozen spec.

## The gap

dbt's native unit-testing framework (`dbt test`, unit tests added in 1.8) only
covers **models** -- there is no way to unit-test a **macro** directly: call it
with given inputs, assert on the rendered SQL/text it produces, or assert it
raises a specific error under bad input.

## Evidence this is a real, still-unmet gap

[`dbt-labs/dbt#10547`](https://github.com/dbt-labs/dbt/issues/10547) --
"[Feature] Unit test support for macros", opened 2024-08-09, **21 👍** (the
clear standout among several dbt feature-request themes checked on 2026-09-17 --
lineage/diff/linter/documentation-themed searches all returned single-digit
reaction counts by comparison).

The issue's own body already describes the workaround people resort to, and why
it's bad -- this is the exact shape a dedicated tool should replace:

> Creating dummy SQL models that call the macros as an alternative to testing
> the macros directly. ... this seems a bit cumbersome and would require these
> test models to be created in the `models/` directory ... which would not be
> desirable as they could conflict with real models and make discoverability
> harder. A dedicated testing project could be created to house these test
> models but would introduce a lot of overhead.

Real, ongoing engagement, not a stale ask -- comments from 2025-02 through
2026-03, including from a dbt Labs PM (`graciegoheen`) actively soliciting use
cases for a native spec as recently as 2026-03-09/10. **As of that date, dbt
Labs itself is still at the "brainstorming a spec" stage, nothing shipped.**
Real use cases already collected in that thread worth re-reading before design:

- Testing macros shared across multiple models/database engines (cross-database
  macro libraries, e.g. utility packages mirroring dbt's own bundled
  cross-database macros).
- Testing *overrides* of dbt's own foundational macros (`generate_schema_name`,
  `ref`, `source`) -- asserting the relation/schema name produced for different
  inputs and environment configs.
- Asserting a macro *fails* under specific bad input (linked from the same
  thread: [dbt-core#12092](https://github.com/dbt-labs/dbt-core/issues/12092)).

User's own reaction on hearing about this (2026-09-17): "それは実際ほしい" (that's
something I'd actually want myself) -- a felt need, not just an abstract metric,
same validation shape that preceded [[dagster-otel-project]] and
dagster-prometheus-exporter.

**Confirmed directly (2026-09-17), not just inferred from the issue:** dbt's own
`unit_tests:` YAML schema requires a `model:` key -- there is no way to point a
unit test at a macro at all. Official docs state plainly that a dict of rows
can't be given to a macro test because dbt can't compile the correct SQL for it.
The exact workaround the GitHub issue describes -- an empty ephemeral model as a
stand-in source, a "validation" model that applies the macro to given input
columns, then a normal unit test *on that validation model* -- is real and
documented independently by multiple people who hit this, not a single
commenter's idea: e.g. ["How to unit test macros in
dbt"](https://medium.com/glitni/how-to-unit-test-macros-in-dbt-89bdb5de8634) and
["Unit Testing dbt Macros: A workaround for dbt's unit testing
limitations"](https://www.dumky.net/posts/unit-testing-dbt-macros-a-workaround-for-dbts-unit-testing-limitations/).
Independent blog posts describing the same workaround is a stronger signal than
the issue's 👍 count alone -- people don't usually write up a workaround unless
they were genuinely blocked by its absence.

## Prior art (2026-11-24)

### `EqualExperts/dbt-unit-testing` -- models only, macro testing explicitly declined

Read from its README and issue tracker via `gh` (the `macros/*.sql` source
itself was **not** read, and only the first 100 issues were scanned).

- A dbt *package* (Jinja macros), not a CLI. MIT, 448 stars. Last release
  v0.4.20 (2025-02-11); recent commits (2026-05) are CI maintenance only, the
  last functional change visible is 2024-07.
- Purpose: unit-test **models** by mocking `ref` / `source` / snapshots / seeds
  (`dbt_unit_testing.test`, `mock_ref`, `mock_source`, `expect`), written as
  SQL files tagged `unit-test` and run with `dbt test --select tag:unit-test`.
  It builds one large SQL query per test, runs it, and prints a diff. It
  predates dbt-core's native unit tests (1.8); its README does not mention
  them.
- To mock `ref` / `source` / `is_incremental` it asks the user to **override
  those macros in their own project** (intrusive, and the source of several
  known limitations in its README).
- Macro testing: nothing in the README. Two issues show the demand and the
  answer:
  - [#157 "How to unit test macros?"](https://github.com/EqualExperts/dbt-unit-testing/issues/157)
    (closed, 2023-07): the maintainer replied on 2024-01-11 that they
    "currently don't have plans to support tests for macros" and pointed to a
    commenter's workaround -- a test file selecting `'{{ my_macro("params") }}'
    as actual` and returning rows where `actual != 'expected output'`.
  - [#215 "Support of unit tests for macros"](https://github.com/EqualExperts/dbt-unit-testing/issues/215)
    (open, 2024-05, no comments): "Currently the only way to do that is to
    define a model that uses the macro and write a test on top of it."

  This is the same dummy-model workaround #10547 describes, reported
  independently by users of a different project -- additional, separate
  evidence of the gap, not a competitor.

How this project differs: it targets macros directly, rides on dbt-core's
native unit tests for execution and comparison instead of building its own SQL
harness, and is configured by YAML under `macro_test/` rather than SQL files
that call test macros.

### Not yet researched

- `yu-iskw/dbt-unittest` (31 stars; "a dbt package provides macros for unit
  testing, inspired by python's unittest module", pushed ~1 month before this
  note). Its README has not been read -- whether and how it supports macro
  testing is unknown. Note: this is a community package, **not** an official
  dbt Labs project.
- Other GitHub results for `dbt-macro-test`-like names (7 repos, 0-1 stars)
  looked like tutorials / samples from their descriptions alone; not opened.
- A multi-word GitHub search for macro-testing tools returned nothing in this
  session (two queries came back empty), so absence of other tools is **not**
  established.

## Motivation and a later goal: coverage for macros (2026-11-24)

First-hand use case (the author's own): at the time they hit this, dbt had no
unit tests at all (before native unit tests in 1.8), and the macros that
hurt were **SQL-snippet-returning macros** (A2 in the inventory). The
underlying motivation is to bring the concept of **coverage** to dbt macros.

**Priority decision (user's call): first make macros testable at all;
coverage comes later.** v1 does not include coverage. It is kept here so the
v1 architecture does not rule it out.

Possible layers, cheapest first (none spiked yet):

1. **Macro-level**: which macros have tests / were actually called during a
   run, with macros used by models flagged first. Static comparison of
   `macro_test/` against defined macros is easy; recording actual calls
   (including nested calls) in-process via `dbtRunner` is plausible but
   unverified.
2. **Line**: which lines of a macro body ran. Either a `coverage.py` plugin
   for Jinja2 (see below) or instrumenting macro source.
3. **Branch**: each side of `if` / `elif` / `else`, `for` with zero vs. some
   iterations, use of argument defaults. Likely the most valuable layer for
   SQL-snippet macros, whose bodies are mostly branching and string assembly.
4. **Dispatch**: which of `default__` / `<adapter>__` implementations are
   exercised (a variant of layer 1).

Architecture notes so v1 does not close the door: tests already run in-process
through `dbtRunner`, which suits tracing/recording; instrumentation that
rewrites macro source would conflict with pointing `macro-paths` at the real
macros directory (it would need generated copies of the macros).

Existing coverage tools found on GitHub (descriptions only, not opened; the
search was shallow, so "nothing else exists" is **not** established):

- `slidoapp/dbt-coverage` (242 stars): docs/test coverage of dbt projects,
  column-level -- not macro code.
- `tnightengale/dbt-meta-testing`, `mikaelene/dbt-test-coverage`: whether
  models have tests.
- `Bilbottom/dbt-unit-test-coverage` (2 stars): code coverage metrics for dbt
  *models'* unit tests.
- `oliverhaas/jinja-coverage` (0 stars): a `coverage.py` plugin for Jinja2
  template coverage. Generic; whether it works with dbt's macro execution is
  unknown.

No tool measuring coverage of macro code itself turned up in these searches.

## Why third-party, not "wait for dbt-core"

dbt Labs is still at the spec-brainstorming stage as of the most recent comment
checked (2026-03). A third-party tool can exist now and fill the gap immediately
-- same relationship this project's sibling ([[dagster-otel-project]]) has to
Dagster's own eventual-but-unshipped native OTel work, and the caution that
comparison implies: if dbt-core ships this natively later, re-evaluate whether
this tool becomes redundant or should adapt (e.g. become a compatibility shim,
or fold useful ideas back), the same way dagster-otel's `#57` now has to
reckon with dbt's *own* (different feature, same lesson) native OTel work.

## Feasibility, verified directly against real dbt-core 1.12.5 (2026-09-17)

Not theoretical -- spiked in a scratch venv (`pip install dbt-core dbt-duckdb`) and
confirmed the actual mechanism dbt itself uses to call a macro is directly
accessible, with no full project/manifest/warehouse-connection needed for the
core case:

```python
from dbt.parser.macros import Macro
from dbt.clients.jinja import MacroGenerator
from dbt.node_types import NodeType

macro = Macro(
    path="macros/greeting.sql",
    macro_sql="{% macro greeting(name) %}Hello, {{ name }}! "
    'default_country={{ var("country", "JP") }}{% endmacro %}',
    original_file_path="macros/greeting.sql",
    package_name="test_pkg",
    resource_type=NodeType.Macro,
    name="greeting",
    unique_id="macro.test_pkg.greeting",
)

gen = MacroGenerator(macro, context={"var": lambda name, default=None: default})
gen("World")  # -> 'Hello, World! default_country=JP'
```

Both confirmed live: a pure-Jinja macro (`add_one(5) -> '6'`, no context needed at
all) and one calling `var()` (context above, output matches expectation exactly).
Key findings from reading `dbt.clients.jinja`/`dbt.parser.macros` directly:

- `dbt.parser.macros.Macro` is a plain constructible object -- just
  `macro_sql`/`name`/`unique_id`/`path`/`package_name`/`resource_type`/
  `original_file_path`. No `Manifest`, no `RuntimeConfig`, no adapter. A tool
  could read a project's `.sql` macro files itself (or even accept
  hand-written macro source directly in a test file) and construct these
  directly -- doesn't need to hook into dbt's own project-parsing pipeline at
  all for this tier.
- `dbt.clients.jinja.MacroGenerator(macro, context)` makes the macro object
  directly callable (`gen(*args, **kwargs)`) -- the exact same call path dbt
  itself uses internally (`CallableMacroGenerator.__call__` ->
  `call_macro`). Whatever the macro's body references (`var`, `config`,
  `return`, `log`, `ref`, ...) just needs to exist as a key in the `context`
  dict -- real or a test-supplied stub.
- `dbt.clients.jinja.UnitTestMacroGenerator` is dbt's own mechanism for
  mocking a macro call during a *model* unit test -- it wraps another
  `MacroGenerator` and replaces `__call__` with returning a fixed
  `call_return_value` instead of actually rendering anything. This is
  exactly the pattern to reuse for stubbing `ref()`/`source()` when testing a
  macro that calls them: same idea (swap in a canned return value), applied
  to the macro-under-test's own dependencies rather than a model's.
- This substantially de-risks Tier 1 (pure-Jinja macros, no `ref`/`source`)
  and most of Tier 2 (macros using `var`/`config`/`return`/`log`, everything
  stubbable the same way `var` was above) -- the "hard part" flagged as
  unvalidated earlier in this doc turns out to have a real, working,
  directly-usable mechanism already, not something requiring a
  from-scratch Jinja reimplementation.
- Still open: `ref()`/`source()` resolution specifically (Tier 2's harder
  edge, and all of Tier 3 -- `generate_schema_name`-style foundational macro
  overrides, adapter-dispatched SQL) needs either the `UnitTestMacroGenerator`
  stub-return-value pattern (simple, but the test author manually supplies
  what `ref()` should return -- no real resolution) or a lightweight real
  `Manifest` (more faithful, much heavier to construct) -- worth prototyping
  the stub-based approach first given how directly it reuses dbt's own
  pattern, before reaching for a full manifest load.

## Design sketch (interface direction settled 2026-09-17; internals still rough)

> **Partly superseded (2026-11-24):** the "no CLI, no YAML DSL, `meta:`-based
> declarative layer" direction below was revised -- see "CLI layer and
> `macro_test/` directory" later in this doc. The Python library described
> here stays as the core; a CLI and a dedicated YAML directory are added on
> top of it.

**Not a new CLI command, not a new YAML DSL -- a small Python library that plugs
into `pytest`.** Now that the core mechanism is confirmed to be plain
constructible Python objects (`Macro` + `MacroGenerator`, see above), inventing
a bespoke test-authoring syntax or a standalone runner would just be
reimplementing what `pytest` already does well (discovery, reporting, CI
integration, `parametrize`, fixtures, mocking via `unittest.mock`/`pytest-mock`
for anything a stubbed context can't cover). A user writes ordinary `test_*.py`
files:

```python
from dbt_macro_test import load_macro


def test_greeting():
    greeting = load_macro("macros/greeting.sql", "greeting")
    assert greeting("World") == "Hello, World!"


def test_generate_schema_name_override():
    fn = load_macro("macros/generate_schema_name.sql", "generate_schema_name")
    assert fn("staging", None) == "staging"
```

`load_macro(path, name, context=None)` is the library's one real job: read the
macro's raw source (parse just the named `{% macro %}` block out of the file --
reusing `dbt.parser.macros`' own block-extraction if it's usable standalone, or
a light regex/Jinja-AST walk otherwise), construct a `dbt.parser.macros.Macro`,
wrap it in `dbt.clients.jinja.MacroGenerator` with a sensible default context
(stubs for `var`/`config`/`return`/`log`, `ref`/`source` raising a clear
"pass `context={'ref': ...}` yourself" error rather than silently doing nothing)
merged with whatever `context` the caller overrides, and return the callable.

**A declarative layer on top, for the simple case (2026-09-17):** the pytest
library above is the required core primitive, but requiring a hand-written
`test_*.py` per macro is more boilerplate than the common case (a macro with a
handful of literal input -> literal output pairs) needs. A second, additive
layer: declare simple cases directly in the macro's own YAML properties file
under `meta:`, and a `conftest.py` helper (using `pytest_generate_tests`) scans
the project's macro YAML for a namespaced key and auto-generates parametrized
tests from it:

```yaml
# macros/schema.yml
macros:
  - name: greeting
    meta:
      dbt_macro_test:
        cases:
          - args: ["World"]
            expect: "Hello, World!"
```

**Confirmed `meta:` is the right (only officially documented) place for this,
not an arbitrary choice** -- checked the actual schema directly
(`dbt.contracts.graph.unparsed.UnparsedMacroUpdate`'s dataclass fields, dbt-core
1.12.5): `name`, `description`, `meta: Dict[str, Any]`, `config: Dict[str, Any]`,
`data_type`, `constraints`, `docs`, `arguments`, and a catch-all `_extra:
Dict[str, Any]`. `meta` is dbt's own documented "arbitrary key-value pairs for
downstream tools" field -- the same convention other dbt-ecosystem tools
(Elementary, dbt-checkpoint, ...) already use for exactly this purpose.
`config` exists too but is conventionally for settings that affect dbt's *own*
behavior (materialization, tags, ...), not third-party tool data. The `_extra`
catch-all means a raw top-level key (not nested under `meta`) probably wouldn't
hard-fail parsing today either, but that's an accident of the current
implementation, not a documented contract -- `meta` is the only choice dbt
actually commits to keeping stable.

This declarative layer only needs to cover literal-in/literal-out cases --
anything needing a custom `ref()`/`source()` stub, `pytest.raises`, or other
non-trivial assertion logic drops to the hand-written `load_macro()` form
instead. Both paths share the same underlying primitive, so this isn't two
implementations to maintain, just two ways of driving one.

Remaining internals to design/spike, independent of the interface question above:

- ~~The block-extraction step -- can `dbt.parser.macros`' own toplevel-block
  parsing... be called standalone~~ **Resolved (2026-09-17), confirmed
  end-to-end against dbt-core 1.12.5 in this repo's own venv, not just a
  scratch one:** yes. The function lives at
  `dbt_common.clients.jinja.extract_toplevel_blocks` -- **not**
  `dbt.clients.jinja` as originally guessed (that name doesn't exist there in
  1.12.5; `dbt.clients.jinja` only re-exports `MacroGenerator` and friends).
  Called with `allowed_blocks={"macro"}, collect_raw_data=False` on a raw
  file's text, it returns `BlockTag` objects with `.block_name`/`.full_block`
  -- no `MacroParser`, no project, no manifest needed. Implemented as
  `load_macro(path, name, context=None)` in `src/dbt_macro_test/__init__.py`,
  covered by passing tests in `tests/test_load_macro.py`.
- Default stub behavior for `ref()`/`source()` -- **implemented** as planned:
  no default resolution, calling either without an explicit `context`
  override raises a clear `RuntimeError` naming what to pass
  (`test_ref_without_stub_raises_clear_error`). `var`/`config`/`log` get
  harmless default stubs.
- Core assertion shapes needed, per the linked use cases in #10547: rendered-
  output equality/pattern match (plain `assert`, nothing special needed) and
  raises-a-specific-error (`pytest.raises`, also nothing special needed) --
  both come for free from being a plain pytest library, which is itself an
  argument for this interface direction.
- ~~Look hard at what `macks22`'s comments in #10547 describe as their team's
  actual macro-testing categorization~~ **Resolved (2026-09-22)** -- see
  "Macro categorization and a richer declarative schema" below.
- **New, added 2026-09-17:** `load_macro_from_manifest(manifest_path,
  unique_id, context=None)` -- a second entry point that skips
  block-extraction entirely by reading an already-generated `manifest.json`'s
  `macros[unique_id]["macro_sql"]` directly (dbt did the extraction when it
  built the manifest). Confirmed working against a real `dbt parse` output.
  Trade-off vs. `load_macro()`: no need to reimplement block-extraction, and
  it's the natural on-ramp to real `ref()`/`source()` resolution later, but it
  requires the caller to run `dbt parse`/`dbt compile` first and the manifest
  can go stale if the macro's source changes without a re-parse.

## A third primitive: real execution against the project's own adapter (2026-09-17)

User pushback on the design so far, and it's correct: for a macro whose *job*
is to render a SQL fragment (the common case -- cross-database utility
macros, `safe_divide`-style expressions, dispatched functions), asserting the
*rendered text* matches a literal string only proves the Jinja logic produced
the text you expected. It doesn't prove the SQL is even valid for the target
dialect, let alone that it computes the right value. Two follow-up ideas were
considered and one was confirmed far better:

- **Rejected as the default: spin up a bundled DuckDB and execute rendered
  SQL there.** Spiked and it works (`duckdb.connect(":memory:")`,
  `case when ... end` executes, `2.5` / `NULL` come back correctly) -- but it
  only proves the SQL is valid *DuckDB* SQL. A macro written for
  Snowflake/BigQuery-specific syntax (`IFF`, `QUALIFY`, backtick-quoted
  identifiers, ...) would either fail or silently mean something different
  under DuckDB. Confirmed directly: `sqlglot.parse_one("select iff(x=0,
  null, y)", dialect="snowflake")` parses fine, but `dialect="duckdb"`
  round-trips it as if it were a real DuckDB function -- no error, wrong
  signal. Bundling one specific engine as *the* execution target doesn't fit
  a tool meant to test macros for whatever warehouse the project actually
  targets.
- **Adopted: reuse the project's own `profiles.yml` and real configured
  adapter, the same way `dbt run`/`run-operation` do.** This is what the
  existing dummy-model workaround (see "Evidence" above) already does under
  the hood -- the pain people report isn't "I have to connect to my real
  warehouse," it's "I have to fake an entire model file and project layout
  just to do it." Confirmed end-to-end against dbt-core 1.12.5 + dbt-duckdb,
  now implemented as `connect_project(project_dir, profiles_dir=None)` +
  `execute_sql(adapter_type, sql)`:

  ```python
  adapter_type = connect_project("path/to/real/dbt/project")
  safe_divide = load_macro("macros/safe_divide.sql", "safe_divide")
  rendered = safe_divide("10", "4").strip()
  assert execute_sql(adapter_type, f"select {rendered} as result") == 2.5
  ```

  Mechanism: `dbt.cli.main.dbtRunner().invoke(["parse", ...])` reads the
  project's real `profiles.yml`/`dbt_project.yml` and registers the real
  adapter as a side effect (`result.result` is the in-memory `Manifest`;
  `result.result.metadata.adapter_type` gives the adapter name).
  `dbt.adapters.factory.get_adapter_by_type(adapter_type)` then retrieves
  that live, already-connected adapter, and
  `adapter.execute(sql, fetch=True)` runs raw SQL through it and returns a
  real `agate.Table`. This is dbt's own adapter-plugin architecture, not a
  bespoke mock -- whatever adapter package is installed (`dbt-snowflake`,
  `dbt-bigquery`, `dbt-postgres`, ...) should work through the identical code
  path, though **only duckdb has been verified directly so far** -- worth
  confirming against at least one non-local adapter before relying on this
  claim.

  Also confirmed directly: `dbt parse` itself never opens a warehouse
  connection, even when the configured connection is unreachable (tested
  with an unreachable Postgres host and a nonexistent DuckDB file path --
  `dbt parse` succeeded both times, and the DuckDB file's parent directory
  was never even created). The connection only happens lazily, inside
  `execute_sql()`'s `adapter.connection_named(...)` block. This means
  `connect_project()` degrades gracefully (fails fast and clearly) if the
  warehouse turns out to be unreachable only once a test actually tries to
  execute something, not at collection/setup time for every test.

  This resolves the "needs real warehouse mocking infrastructure that's a
  project of its own" concern from the previous version of this doc --
  no mocking is needed at all; the tool rides on the project's own adapter.

Updated three-primitive shape, all implemented and passing in
`src/dbt_macro_test/`:

| primitive | verifies | needs a DB connection |
|---|---|---|
| `load_macro()` | rendered text, from a raw `.sql` file | no |
| `load_macro_from_manifest()` | rendered text, from an existing `manifest.json` | no |
| `connect_project()` + `execute_sql()` | the *executed result* of rendered SQL, against the project's real configured warehouse | yes, lazily, via the project's own profile |

## Macro categorization and a richer declarative schema (2026-09-22)

Prompted by the user independently re-deriving the same split during design
discussion ("macroって色々あるじゃないですか、udfみたいなのもあれば、select
全部返すやつみたいな" -- macros vary a lot, some are UDF-like, some return an
entire SELECT) -- resolved the "look hard at macks22's comments" item flagged
above by actually reading the full comment, not just its existence:
[dbt-labs/dbt#10547#issuecomment-4034571549](https://github.com/dbt-labs/dbt/issues/10547#issuecomment-4034571549).
`macks22` (GitHub bio: "ML Engineer, Data Scientist/Engineer", no dbt Labs
affiliation) runs macro unit testing in production against Snowflake at their
own company, and wrote this in direct response to dbt Labs PM
`graciegoheen`'s request for real use cases -- a stronger source than the
issue's reaction count alone, same evidentiary reasoning as the independent
blog-post workarounds already cited above.

### Their categorization

Three buckets:

1. **Pure Jinja** -- the main target, and this project's main target too.
   Includes macros whose sole job is producing a SQL snippet (this project's
   `safe_divide` fixture is exactly this shape) -- but macks22 flags this
   specific case as a **grey area even for their own team**: asserting on
   the rendered SQL *string* "doesn't mean a lot semantically, and doesn't
   scale to longer, more complex SQL outputs." Their own tooling has no
   answer to this beyond string comparison.
2. **Generic test macros** (`test_*`) -- a genuinely separate contract, not
   just "a macro": takes relation/column arguments, has its own config
   surface (`fail_calc`, `where`, `severity`, `error_if`), and needs
   verifying pass/fail row-count semantics (0 rows = pass) plus which node
   types it's valid against (model/column/seed/source).
3. **Everything else** (materializations, hooks) -- macks22's team punts
   entirely here: "requires integration tests, i.e. testing through a
   model." Explicitly out of scope for unit testing, by their own
   assessment, not an oversight.

**This confirms `connect_project()`/`execute_sql()` (previous section) is a
genuine improvement over the state of the art described here, not a
redundant nice-to-have.** It's specifically an answer to the grey area
macks22 flags in (1) as unsolved by their own team's tooling: instead of
comparing rendered SQL *text*, execute it against a real adapter and assert
on the *result*. Category (2) is a real, distinct gap this project doesn't
cover at all yet (see Open questions below) -- not something to silently
fold into the plain-macro case, since it has its own argument/config/scope
contract. Category (3) staying out of scope matches this project's own
existing boundary already (real adapter execution via the project's own
profile, not a from-scratch materialization harness) -- no new gap found
there.

### Their proposed YAML shape -- `overrides` / `given` / `expect`

Worth adopting the core mechanism directly rather than re-deriving: every
value in macks22's sketch can be tagged `type: literal` (default, a plain
YAML scalar) or `type: jinja` (a Jinja expression, evaluated once at
test-build time to produce the real value). This is a materially better
answer than this project's own prior in-conversation sketch (a flat
`context: {refs: {...}, sources: {...}}` mapping, never committed to this
file) to the open question raised in that same discussion -- "how does a
human write a non-literal Python object, like a stubbed `Relation`, in YAML
at all." Rather than inventing a bespoke sub-schema per kind of override
(refs vs. sources vs. arbitrary macro mocks), one mechanism (`type: jinja`)
covers all of them uniformly:

```yaml
macros:
  - name: uses_ref
    meta:
      dbt_macro_test:
        cases:
          - name: with_ref_stub
            overrides:
              macros:
                ref:
                  type: jinja
                  value: "{{ api.Relation.create('analytics', 'my_model') }}"
            given:
              arguments: []
            expect:
              returns:
                value: "select * from analytics.my_model"

  - name: safe_divide
    meta:
      dbt_macro_test:
        cases:
          - name: division_by_zero_is_null
            given:
              arguments:
                - "10"
                - "0"
            execute: true          # this project's own addition, not macks22's
            expect:
              returns:
                value: null
```

`expect` itself also generalizes cleanly onto this project's needs:
`expect.returns` (this project's plain rendered-text/executed-value case),
`expect.error`/`expect.warning` (this project's not-yet-designed
`expect_error:`, loosely sketched in the same conversation) -- with the
error/warning message match also typed `literal` (substring/exact) or
`jinja` (an arbitrary boolean expression, e.g. `{{ "ref" in message }}`).
This subsumes the "do we need a separate regex-match key" question raised
in the same discussion: `jinja` already covers regex via a filter
(`|regex_search`) if actually needed, so no new key is required.

### Open questions, added 2026-09-22

- Generic test macros (#2 above) are a distinct feature, not covered by the
  current three primitives at all -- `given.arguments` would need a `data`
  argument type (relation-shaped fixture input, "just like inputs in unit
  tests for models" per macks22) this project has no equivalent of yet.
  Decide: in scope for v1, or a tracked follow-up once the plain-macro case
  ships? (Leaning follow-up -- it's a different enough contract that
  bundling it into v1 risks delaying the core pure-Jinja case, which is
  where the strongest evidence of demand is.)
- Adopt `overrides`/`given`/`expect` (macks22's nested shape) wholesale, or
  keep this project's flatter `args`/`context`/`expect` sketch and only
  borrow the `type: literal|jinja` mechanism? The flatter shape is less
  boilerplate for the common case (a plain scalar in, scalar out); the
  nested shape scales better once `overrides`/`data`-typed arguments are
  actually needed. No strong evidence yet for which shape this project's
  own intended usage looks more like day to day -- revisit once tried
  against a real project's macros, not decided from first principles alone.
- `type: jinja` values are evaluated *once, at test-build time* in macks22's
  sketch -- no per-call dynamic behavior (e.g. "return X on the first call,
  Y on the second"). That's a real, cited limitation of their *current*
  (non-declarative, model-var-based) workaround, not necessarily a
  constraint they want carried into a new spec. Their "must-have #3" (assert
  on *arguments passed to* an overridden macro -- a real mock, not just a
  stub) is not solvable by a static `type: jinja` value either way. Open
  whether this project attempts that must-have at all, or explicitly punts
  on mock-style assertions the same way it already punts on
  materializations/hooks (category 3 above).
- Still open from the same discussion: which project `execute: true`
  connects to by default -- walk up from the macro file to find
  `dbt_project.yml` automatically, vs. requiring `project_dir:` explicit
  per case or per file.
- Resolved from the same discussion: the separate "match style" question
  (`expect_match:` as its own key) -- no new key needed, `type: jinja` on
  the message/value already covers arbitrary predicates including regex.

## Test-target inventory: kinds of macros worth testing (2026-11-24)

An enumeration of macro kinds, built from the categorization above plus the
full read of #10547 (issue body and all comments through 2026-03-10). This is
a catalogue of *what could be tested*, not a v1 scope decision -- scope is
still open (see the end of this section).

### A. Pure Jinja (primary target)

| # | Kind | Examples | What to assert |
|---|---|---|---|
| A1 | Scalar-returning, UDF-like | `cents_to_dollars`, string formatting, date math | args -> return value; type (str/int/list/dict); `none` / empty handling |
| A2 | SQL-snippet-returning | `safe_divide`, `date_trunc_week(col)`, `surrogate_key([cols])` | rendered SQL (whitespace-normalized); executed result via `execute_sql` |
| A3 | Whole-SELECT-returning | `union_relations`, `pivot`, `star(from, except=[...])` | long SQL is weak under string comparison -> prefer executed result |
| A4 | Branch-heavy | `if/elif`, `var()` present/absent, per-`target.type` output | one case per branch; var/env overrides |
| A5 | Loops / collections | `for col in columns`, dict/list ops, `namespace` | empty, single, many; ordering |
| A6 | Error-raising | `exceptions.raise_compiler_error`, arg validation | exception type and message; `warn` firing |
| A6' | SQL-execution-time error | query fails on bad input (e.g. a `json_to_map` given a non-object JSON) | error raised by the warehouse, distinct from a Jinja render-time error |
| A7 | Default args / kwargs | `macro foo(a, b=none, *args, **kwargs)` | omitted args; positional vs. keyword |
| A8 | Composition | macro A calls macro B | behavior with B stubbed/overridden |
| A9 | Composite return types | arrays, structs, maps | executed result with a composite type; per-adapter expected value |
| A10 | Recursive | few-hundred-line recursive Jinja | termination, depth, base case |

### B. Depends on dbt context

| # | Kind | Examples | What to assert |
|---|---|---|---|
| B1 | Uses `ref()` / `source()` | `uses_ref` (fixture exists) | stubbed ref/source -> resolved relation name |
| B2 | Reads `this` / `model` / `config` | `config.get('x')`, `model.name` | substituted context |
| B3 | `adapter.dispatch` | `cross_db_datediff`; `default__`, `duckdb__`, `snowflake__` | which implementation is selected; dispatch order |
| B4 | Calls `adapter.*` | `get_columns_in_relation`, `get_relation`, `quote`, `type_string()` | needs a real adapter (`connect_project`) |
| B5 | `run_query` / `statement` | dynamic column lists, distinct values | `execute: true` only; fixture tables |
| B6 | `generate_*_name` overrides | `generate_schema_name` (fixture exists), `generate_database_name`, `generate_alias_name` | custom name present/absent; per-target / per-environment naming |
| B7 | `target` / `env_var` / `var` dependent | prod/dev switching, CI detection | per-environment output; error when unset |
| B8 | `is_incremental()`-style flags | incremental `where` clauses | flag on and off |
| B9 | Overrides of `ref` / `source` themselves | environment-aware relation resolution | the produced relation under different inputs/configs (issue body's own example) |
| B10 | Reads `graph` / `selected_resources` / `execute` | macros that walk the graph | overridden global context |

### C. Generic test macros (`test_*` / `{% test %}`)

- C1 -- returned SELECT yields 0 rows (pass) vs. >= 1 row (fail) on given data
- C2 -- effect of `where`, `severity`, `error_if`, `warn_if`, `fail_calc`
- C3 -- applicability to model / column / seed / source
- C4 -- relation-shaped fixture input (`data`-typed argument)

Already tracked as a separate contract and a likely post-v1 follow-up (see
"Open questions, added 2026-09-22").

### D. Candidates for out of scope (integration-test territory)

| # | Kind | Reason |
|---|---|---|
| D1 | Custom materializations | only verifiable through a model |
| D2 | `pre_hook` / `post_hook` / `on-run-start` / `on-run-end` | depends on the run lifecycle |
| D3 | Side-effect-only macros (`log()`, `print()`) | no return value; only observable in logs |
| D4 | DDL/DML-issuing macros (`create_table_as`, `grant`, `drop_*`) | need DB-state inspection (though duckdb may make this feasible) |
| D5 | `run-operation` macros | return value unused; side effects are the point |

### Cross-cutting axes

- **Input:** literal / Jinja expression / Relation object / `none` / empty / wrong type
- **Output:** rendered string, return object, executed result, exception, warning
- **Environment:** adapter type (duckdb only vs. checking dispatch targets), `var`, `env_var`, `target`
- **Dependency substitution:** ref/source, other macros, adapter methods (stub vs. mock with call assertions)
- **Package macros:** whether external-package macros (`dbt_utils.*`) are in scope
- **Adapter-specific expected values**, **parametrization**, **per-macro shared fixtures**

### What #10547 adds to this inventory

The inventory above was cross-checked against every concrete use case in the
issue. Mapping of source to row:

- Issue body (`jas-grover`, 2024-08-09): reused logic across models, and
  overriding `ref`/`source` -> A1-A4, **B9**.
- `james-johnston-thumbtack` (2025-06-20,
  [comment](https://github.com/dbt-labs/dbt/issues/10547#issuecomment-2990214774)):
  a shared multi-engine utility package, few-hundred-line recursive Jinja,
  asserting on actual warehouse output for arrays/structs/maps, per-adapter
  expected output, and a macro that must fail on non-object JSON -> **A9**,
  **A10**, **A6'**, B3, B4.
- `graciegoheen` (dbt Labs, 2026-03-09,
  [comment](https://github.com/dbt-labs/dbt/issues/10547#issuecomment-4026249337)):
  `generate_schema_name` override in CI, driven by `env_vars`, an
  `is_running_in_ci` macro and `target.schema` -> B6, B7. This is the use
  case dbt Labs itself chose to lead with.
- `macks22` (2026-03-10,
  [comment](https://github.com/dbt-labs/dbt/issues/10547#issuecomment-4034571549)):
  three-bucket categorization (already covered above), plus five must-haves
  for pure-Jinja macros:
  1. arguments as Jinja or literals, including Relation objects (today's
     `var`-in-a-wrapper-model workaround only passes strings);
  2. overriding macros, including a macro called multiple times returning
     different values per call, and builtin-package macros (`exceptions`,
     `adapter`), which cannot be overridden today;
  3. asserting on the arguments passed to an overridden macro (mock-style);
  4. asserting on exceptions and warnings *including messages*;
  5. overriding global context (`target`, `execute`, `graph`,
     `selected_resources`) -> **B10**.
  Nice-to-haves, probably not a first release: pytest-style
  parametrization, shared per-macro fixtures.
- `#12092` (referenced, not read): testing that a macro fails as expected
  -> A6.

Not found in the thread: any request about materializations, hooks, or
`ref`/`source` mocking beyond the issue body -- consistent with D1/D2 staying
out of scope. No dbt Labs commitment beyond the `Refinement` label and the
`graciegoheen` spec proposal.

### Design implications

- dbt Labs' own proposed shape (`graciegoheen`, 2026-03-09:
  `macro:` / `overrides:` / `given:` / `expect: returns:`) is close to
  `macks22`'s `overrides`/`given`/`expect`, which the previous section
  already leans toward adopting. If dbt-core ships a native spec it will
  likely look like this, so staying shape-compatible lowers migration cost.
- dbt Labs' proposal puts entries under a top-level `unit_tests:` key with a
  `macro:` field; this project currently keys off `meta.dbt_macro_test` in
  `macros/schema.yml`. Whether to align key names with dbt Labs' sketch (to
  ease a later move to the native feature) is undecided.
- Must-haves 2-4 (multi-call stubs, overriding builtin macros, call
  assertions) are not solvable by a static `type: jinja` value; this sharpens
  the existing open question about whether to attempt mock-style assertions
  at all.
- Latest comment seen in the issue is 2026-03-10. The "Next step" re-check
  of whether dbt-core has shipped or spec'd anything remains outstanding as
  of 2026-11-24.

### Open: v1 scope

Not decided. Candidate cut: A (all) plus B1 / B3 / B6 for v1; B4 / B5 / B9 /
B10 and C as follow-ups. Further open points: how far B3 goes (duckdb only vs.
verifying other adapters' implementations as text), and whether A3-style
large SQL should default to executed-result comparison over string
comparison.

## CLI layer and `macro_test/` directory (2026-11-24)

**Decision (user's call, 2026-11-24): add a dedicated CLI and a dedicated
test-spec directory, on top of the existing Python library.** This revises
the earlier "not a new CLI, `meta:`-based declarative layer" direction.

### Architecture

```
dbt-macro-test run [--select ...] [--project-dir ...] [--target ...]
        |
        v
 load YAML spec -> expand cases -> execute -> report
        |
        v
 load_macro / connect_project / execute_sql   (existing three primitives)
        ^
        |
 pytest  (complex cases stay hand-written, as before)
```

Why a CLI: the intended audience is largely analytics engineers who don't
write Python; dbt Labs' own proposal is YAML-first, not pytest-first; result
display, exit codes, `--select` and `--target` are CLI concerns that fit
poorly into `pytest_generate_tests`; and CI can run it without pytest.

Why a standalone executable, not a `dbt` subcommand: dbt-core, as far as is
currently understood, has no plugin mechanism for adding CLI subcommands
(**not verified** -- check before relying on it). The tool still drives dbt
internally via `dbtRunner`, so profile / manifest / adapter resolution stay
dbt's job.

Why keep the pytest library: `pytest.raises` and `unittest.mock` cover what
YAML can't express well (a macro called multiple times returning different
values, asserting on arguments passed to an overridden macro -- macks22's
must-haves 2-4 in #10547), and it is already implemented and passing.

### Layout

```
my_dbt_project/
  dbt_project.yml
  macros/
    utils/safe_divide.sql
    generate_schema_name.sql
  macro_test/                      # same role as dbt's own tests/
    utils/safe_divide.yml          # mirrors the macros/ path
    generate_schema_name.yml
    fixtures/                      # CSVs etc. for data-typed args / expected rows
```

- Dedicated directory, **not** `meta:` in `macros/schema.yml` -- keeps the
  specs out of dbt's own parse results and out of `schema.yml`. (That dbt
  ignores unknown top-level directories is the expected behavior, not yet
  verified here.)
- Directory structure mirrors `macros/` for discoverability and `--select`,
  but it is a convention only: the file's own `macro:` field is what
  identifies the macro under test (also needed for package macros such as
  `dbt_utils.star`).
- Directory name overridable with `--test-dir`, so a later rename (the
  project/command name is still a placeholder) stays cheap.

### Spec shape

Top level is a `macros:` list, so one file can hold several small macros.
`given.arguments` is a **map keyed by parameter name**, not a positional
list:

```yaml
# macro_test/utils/safe_divide.yml
macros:
  - macro: safe_divide
    cases:
      - name: division_by_zero_is_null
        given:
          arguments:
            numerator: 10
            denominator: 0
        expect:
          result:                # executed on the project's real adapter
            sql: "null"          # expected value, as a SQL expression

      - name: relation_arg
        given:
          arguments:
            relation:
              type: jinja
              value: "{{ api.Relation.create('analytics', 'my_model') }}"
```

`overrides` / `given` / `expect` with `type: literal | jinja` follow the
nested shape already leaned toward above (close to dbt Labs' own proposal,
so a mechanical conversion to a `unit_tests:`-style list stays possible).

### Argument matching

The macro's declared signature (`{% macro safe_divide(numerator,
denominator=none) %}`) is read -- expected from the Jinja AST's
`nodes.Macro` `args` / `defaults`, **not yet spiked in this repo** -- and the
case is validated before running:

- unknown argument name -> error (catches typos)
- a parameter without a default is missing -> error
- a parameter with a default is omitted -> macro's default is used (doubles
  as the A7 test)
- `*args` / `**kwargs` can't be named: reserved keys `varargs: [...]` /
  `kwargs: {...}` are an option, or leave unsupported initially (rare)
- a positional list for `arguments` may be accepted as a shorthand later,
  but the map is the documented form; start with the map only

Values are passed as YAML typed them (`10` is an int, `"10"` a string). For
macros that interpolate into SQL via `{{ }}` the two render identically;
anything needing an object (a `Relation`) uses `type: jinja`.

### Comparison: follow dbt's official unit-test approach (2026-11-24)

**Decision (user's call): compare the way dbt's own unit tests do, not by
pushing the comparison into the database.** Read directly from the installed
dbt-core 1.12.5 source:

- **DB side** (`dbt/include/global_project/macros/materializations/tests/unit.sql`,
  `get_unit_test_sql`): run the SQL under test (`actual`) and the expected
  fixture as SQL (`expected`), tag each with an `actual_or_expected` column,
  and return both with a single `union all`. **No comparison happens in SQL.**
  The expected side is built by `get_expected_sql(expected_rows,
  column_name_to_data_types, ...)`: the actual query's column types are read
  first (`get_columns_in_relation` on an empty temp table) and the expected
  values are cast to those types in the DB.
- **Python side** (`dbt/task/test.py`, `_get_unit_test_agate_table`,
  `_get_daff_diff`): split the returned agate table on `actual_or_expected`,
  sort both sides (so row order is ignored unless `ordered`), and diff with
  `daff`. Any difference fails the test and the daff diff is rendered as the
  failure message. `daff` already ships as a dbt-core dependency.

An earlier idea in this discussion -- compare in the DB with `is not
distinct from` / two-way `EXCEPT` -- is **dropped**: it diverges from the
official behavior, runs into `EXCEPT`/`GROUP BY` limits on array/JSON types
in some warehouses (BigQuery), and loses daff's readable failure diff.

Resulting `expect` kinds:

| `expect` | produced by | compared |
|---|---|---|
| `returns` | the macro's own return value (text/object), no DB | in Python, plain equality |
| `result` | rendered SQL executed on the project's adapter (A2, A3, A9) | actual rows vs. expected rows (SQL expression or `fixtures/` CSV cast to the actual column types), union-all'd then daff-diffed in Python |
| `error` / `warning` | the macro raising / warning | message match (A6; execution-time errors from the warehouse are caught as exceptions, A6') |

`execute: true` is no longer a separate flag; `expect.result` implies
execution. This replaces the earlier `execute_sql(...) == 2.5` style in "A
third primitive", where the value was pulled out and compared with Python `==`
and no type alignment was done.

Implementation notes / still to verify (not yet spiked in this repo):

- Reuse dbt's own macros (`get_unit_test_sql`, `get_expected_sql`) through the
  adapter vs. re-implementing the union-all in this tool. Reusing keeps
  behavior identical to official unit tests but ties us to dbt-core internals.
- How array / struct / map values come back through agate on duckdb and
  whether they diff correctly in daff (expected from reading
  `list_rows_from_table`, but unconfirmed for composite types -- the one case
  where the DB-side alternative would have been better).
- Floating-point tolerance: daff compares values as returned; a `tolerance`
  option would need to be handled in Python before diffing.

### Principle: stay as close to official dbt as possible; spike results (2026-11-24)

**Decision (user's call):** this tool should be a *translation layer onto
dbt's official unit tests*, not a parallel comparison engine. `macro_test/*.yml`
is turned into (a) a throwaway model per case, `select {{ macro(args) }} as
result`, and (b) a native `unit_tests:` entry with `given: []` and
`expect: rows:`, then run through dbt itself (`dbt test --select
test_type:unit`, via `dbtRunner`). Comparison, type casting and failure
rendering are then dbt's own. Spec keys should borrow the official unit-test
vocabulary (`overrides: macros/vars/env_vars`, `given`, `expect.rows` with
`format: dict|csv|sql` and `fixture:`) rather than inventing new ones; the
earlier invented `expect.result.sql` is superseded by `expect.rows`.

Spiked on dbt-core 1.12.5 + dbt-duckdb 1.11.0 in a scratch project (not in
this repo):

- A model containing only `select {{ safe_divide(10, 4) }} as result` plus a
  unit test with `given: []` and `expect: rows: [{result: 2.5}]` **passes**;
  `{result: null}` for `safe_divide(10, 0)` passes too. No input rows are
  required.
- A deliberately wrong expectation **fails** with dbt's normal diff
  (`Decimal('2.5')` vs `Decimal('9.9')`) -- the comparison is real, not
  vacuously passing.
- **Composite types work:** one model returning a list, a struct and a map
  (`[1, 2, 3]`, `{'a': 1, 'b': 'x'}`, `map {'k1': 1, 'k2': 2}`) passes with
  `expect: rows: [{l: [1, 2, 3], s: {a: 1, b: x}, m: {k1: 1, k2: 2}}]`, and
  wrong list/map values fail with a per-cell diff. This resolves the one worry
  about the official approach (arrays/structs/maps through agate/daff), at
  least on duckdb.
- **The user's `models/` need not be touched:** a separate *generated*
  project directory holding only the throwaway models and the `unit_tests:`
  YAML, with `macro-paths` set to an **absolute path** at the real project's
  macros, loads and runs them (macros were resolved from the other
  directory).

**Second spike (2026-11-24): carrying project settings into the generated
project.** Scratch setup: a "user" project with `vars`, a `dispatch:` config,
a local package providing a dispatched macro (`default__` + `duckdb__`
implementations), and user macros using all three.

- Without carry-over, as expected, it breaks: `Required var 'country' not
  found`, and the dispatch override silently doesn't apply (the package's
  `duckdb:a` is returned instead of the user's `user:a`) -- a **silent wrong
  result**, not an error, so carry-over must be done deliberately.
- Carried over: `vars`, `dispatch`, `packages.yml` (then `dbt deps` in the
  generated dir, a local package here), `macro-paths` -> absolute path of the
  real macros. With these, a package macro (`pkg_double`) works, `vars`
  resolve (`JP`), and the unit test's own `overrides: vars: {country: US}`
  works too.
- **The generated project's `name:` must equal the real project's name.**
  The `dispatch` `search_order` refers to packages by name, and macros loaded
  via `macro-paths` take the *root project's* name as their package. With
  `name: gen` the user's dispatch override was ignored (silent, as above);
  with the same name it passed (3/3).
- The generated dir also needs `dbt deps` run (dbt errors clearly if not:
  "expects 1 package(s) ... found only 0").
- Not tried: remote packages such as `dbt_utils` (needs network; the local
  package exercises the same `packages.yml` / `dbt deps` path), `quoting`,
  `flags`, and `profiles.yml` target selection (the spike reused one profile).

**Goal (user's call, 2026-11-24): zero-config usage.** Pointing the tool at
`macro_test/` (default `./macro_test`) should be all a user does:

```
cd my_dbt_project
dbt-macro-test run [path] [--target ci]
```

Project root = nearest ancestor of `macro_test/` containing `dbt_project.yml`
(this also answers the earlier open question about which project `execute`
connects to); `profiles.yml` resolution is left to dbt's own rules; carry-over
is internal. This is why carry-over is "take everything, change a few keys",
not a per-setting copy list.

**Third spike (2026-11-24): the whole pipeline end to end.** A throwaway
script (scratch dir, not in this repo) implementing:

1. `root` = walk up from the test dir to `dbt_project.yml`.
2. `cfg = dbt.config.project.load_raw_project(root)` -- dbt-core's own loader
   (returns the raw dict; Jinja such as `env_var()` is left for dbt to render).
3. Generated `dbt_project.yml` = `cfg` with: `model-paths` -> `["models"]`
   (generated dir), `macro-paths` -> each original path made absolute,
   `seed/snapshot/analysis/test-paths` -> `[]`, `on-run-start`/`on-run-end`
   removed; everything else (`name`, `profile`, `vars`, `dispatch`, ...) kept
   as-is. Written under `<root>/target/macro_test/`.
4. `packages.yml` copied, `dbtRunner().invoke(["deps", ...])` run.
5. `macro_test/**/*.yml` -> one `select {{ macro(kwargs) }} as result` model
   per case + one native `unit_tests:` entry per case (`given: []`, `expect`
   and `overrides` passed straight through). YAML values are rendered to Jinja
   literals (`None` -> `none`, strings via JSON quoting, lists/dicts
   recursively).
6. `dbtRunner().invoke(["test", "--select", "test_type:unit", "--project-dir",
   <generated>])`, with cwd = project root and no `--profiles-dir`.

Input project: two `macro-paths`, a `var` defined as `"{{ env_var('MT_COUNTRY',
'JP') }}"`, a `dispatch:` override, a local package in `packages.yml`, an
`on-run-start` hook, a `models:` config block, and `profiles.yml` only in the
project root. Result: **4/4 unit tests PASS** -- macros from both
`macro-paths`, the Jinja-rendered `var`, the dispatch override, the package
macro, a per-case `overrides: vars` and profile resolution all worked.
Confirmed along the way:

- **`on-run-start` hooks do run under `dbt test`** (with the hook kept, the
  run reported "1 project hook" and counted it as a result). Removing
  `on-run-start`/`on-run-end` in step 3 is therefore required, not
  precautionary.
- A kept `models:` config block caused no warning in this run (it matched the
  project's own name; a block naming a nonexistent package/path might warn --
  not tried).
- Running with no `--profiles-dir` resolved `profiles.yml` from the cwd, i.e.
  plain dbt rules apply as long as cwd is the project root.

Still to check:

- Not exercised in this spike: the `env_var` default being *overridden* by a
  real environment variable, remote packages (`dbt_utils`) and reusing the
  real project's `dbt_packages/` to avoid network, `selectors.yml` /
  `dependencies.yml`, and a `models:` block that names a nonexistent path.
- Macros using `ref()` / `source()` (unit tests will then require `given:`
  inputs for those relations, as for any model).
- Whether a macro that raises (`exceptions.raise_compiler_error`) surfaces
  usefully through the unit test (status/message), or whether `error` /
  `warning` expectations must stay on the `load_macro()` path as planned.
- Non-duckdb adapters (still deferred, per Open questions).
- Per-test cost of generating files and re-parsing (a full parse ran each
  time in the spike; ~1-2 s on a tiny project).

### Still open from this decision

- Project-wide settings (`project_dir`, `profiles_dir`, target): start with
  CLI flags plus defaults relative to `dbt_project.yml`, no dedicated config
  file.
- Where hand-written pytest tests live: inside `macro_test/` (`test_*.py`)
  vs. the user's own `tests/` (which collides with dbt's `tests/` for
  generic/singular tests).
- Command / package name (still the `dbt-macro-test` placeholder).
- Everything under "Open: v1 scope" above.

## Open questions

- **Narrowed (2026-09-17):** the adapter-mocking scope worry is resolved (see
  above) -- reuse the real adapter, don't mock. Whether the
  `dbtRunner`/`get_adapter_by_type()` path behaves identically for a real
  cloud adapter (Snowflake/BigQuery/Postgres) vs. duckdb's embedded/no-server
  case is technically still unverified, but **decided (2026-09-17, user's
  call) not to chase that now** -- duckdb is good enough to keep developing
  against; revisit only if something duckdb-specific turns out to leak
  through (e.g. connection lifecycle assumptions that don't hold for a real
  server-based adapter).
- Whether/how a pytest fixture that calls `connect_project()` should be
  provided out of the box (a `conftest.py` helper, similar to
  `sample_adapter_type` in this repo's own `tests/conftest.py`) vs. left
  entirely to the user to wire up per-project.
- Naming -- `dbt-macro-test` is a placeholder, not decided.

## Next step, whenever this gets picked up

Re-check #10547 for whether dbt Labs has shipped or spec'd anything since
2026-09-22 before continuing -- the whole premise of "third-party, not wait"
needs re-confirming if time has passed.

As of 2026-09-22, the immediate next steps are:

- Settle the two real forks flagged in "Macro categorization and a richer
  declarative schema" above: nested (`overrides`/`given`/`expect`) vs. flat
  (`args`/`context`/`expect`) YAML shape, and whether generic test macros
  are in scope for v1. Both block writing the actual YAML-loading code, not
  just bikeshedding -- pick one shape and implement it rather than designing
  further in the abstract.
- Decide the declarative YAML layer's file location (`meta:` in the same
  schema.yml vs. a separate `*.macro_test.yml`, see the `meta` discussion
  from 2026-09-17) -- deferred, not load-bearing for the core primitives.
- Keep developing against duckdb as the reference adapter (decided
  2026-09-17, see Open Questions) -- non-embedded adapter verification is
  deferred, not blocking.
- The repo itself now has real scaffolding worth knowing about for future
  sessions: `uv`-managed (`pyproject.toml`, `.venv`), source at
  `src/dbt_macro_test/__init__.py`, tests at `tests/` (including a scratch
  dbt project at `dev/sample_project/` used by `tests/conftest.py`'s
  fixtures), a VS Code workspace file at `dbt-macro-test.code-workspace`.
