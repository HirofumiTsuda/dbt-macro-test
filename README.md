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

## Development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```
