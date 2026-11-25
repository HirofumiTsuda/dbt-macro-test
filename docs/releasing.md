# Releasing

A release is made by the maintainer, by pushing a tag. Nothing is published without the approval of
the `pypi` environment in GitHub, and a version number on PyPI can never be used again, so a
mistake is fixed in the next version.

## Once, before the first release

These are settings of PyPI and GitHub, not of the repository, and are the maintainer's.

1. **PyPI, trusted publishing** (no token is stored anywhere). The project does not exist yet, so
   add a *pending* publisher at <https://pypi.org/manage/account/publishing/>:
   project `dbt-macro-test`, owner `HirofumiTsuda`, repository `dbt-macro-test`, workflow
   `release.yml`, environment `pypi`. The same on <https://test.pypi.org/manage/account/publishing/>
   with the environment `testpypi`.
2. **GitHub environments** (Settings, Environments): `pypi`, with *Required reviewers* set to
   the maintainer (this is the approval), and, if wanted, a rule that only tags may deploy to it;
   and `testpypi`.
3. **A dry run on TestPyPI**: Actions, Release, *Run workflow*, on a branch whose `pyproject.toml`
   has a version that TestPyPI has not seen (such as `0.1.0.dev1`, with a matching heading in
   `CHANGELOG.md`). It runs the whole of the release except the last step, and publishes to TestPyPI.
   Then, in a new environment:

   ```bash
   pip install dbt-duckdb
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ dbt-macro-test==0.1.0.dev1
   dbt-macro-test --help
   ```

## For each release

1. Choose the version (`0.1.0`, `0.2.0`, ...; before 1.0.0 a minor version may change the spec format).
2. In a pull request: set `version` in `pyproject.toml`, and in `CHANGELOG.md` rename the heading of
   the version to `## [X.Y.Z] - YYYY-MM-DD` and list what changed. The pull request runs the build
   and the smoke test of the release, so the package is known to be sound before the tag.
3. After it is merged, tag the merge commit and push the tag:

   ```bash
   git switch main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. The workflow builds the package and checks that the tag, `pyproject.toml` and `CHANGELOG.md`
   agree; installs the wheel and the sdist, each into a clean environment, and runs them on a
   project; and then waits for the approval of the `pypi` environment. Approve it in the run's page.
5. Check <https://pypi.org/project/dbt-macro-test/>, and install it into a new environment.

## What the workflow checks

- the tag is `v` plus the version in `pyproject.toml`, and `CHANGELOG.md` has a heading for it;
- `twine check --strict` passes, and the wheel holds `py.typed` and `LICENSE`, the sdist `LICENSE`;
- the wheel and the sdist each install into a new environment, `dbt-macro-test` is the installed
  one (not the checkout), and `dbt-macro-test run` passes on the project in `tests/fixtures/project`.
