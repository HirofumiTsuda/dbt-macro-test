# Releasing

A release is made by the maintainer, by pushing a tag. Nothing is published without the approval of
the `pypi` environment in GitHub, and a version number on PyPI can never be used again, so a
mistake is fixed in the next version. The steps, and what Claude checks and does not do alone, are
also in the skill `.claude/skills/release/SKILL.md`; change both when the way changes.

## Once, before the first release

These are settings of PyPI and GitHub, not of the repository, and are the maintainer's.

1. **PyPI, trusted publishing** (no token is stored anywhere). The project does not exist yet, so
   add a *pending* publisher at <https://pypi.org/manage/account/publishing/>:
   project `dbt-macro-test`, owner `HirofumiTsuda`, repository `dbt-macro-test`, workflow
   `release.yml`, environment `pypi`. The same on <https://test.pypi.org/manage/account/publishing/>
   with the environment `testpypi`.
2. **GitHub environments** (Settings, Environments): `pypi`, with *Required reviewers* set to
   the maintainer (this is the approval), and, if wanted, a rule that only tags may deploy to it;
   and `testpypi`. **Make `pypi` before the first tag.** A job that names an environment that does
   not exist makes it on the spot with no rule, and then does not wait for anyone: the release
   would be published without the approval. (`testpypi` was made that way by the first dry run.)
   Check with `gh api repos/HirofumiTsuda/dbt-macro-test/environments`.
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
   the version to `## [X.Y.Z] - YYYY-MM-DD` and list what changed, **starting with a paragraph that
   says what the version is for** (under the heading, before the first `###`): it is the head of the
   GitHub release. The pull request runs the build and the smoke test of the release, so the package
   is known to be sound before the tag, and it stops at a version without that paragraph.
   **For the first release**, the README says that the tool is not on PyPI and installs it from git;
   the PyPI page of a version is the README as it was built, so change the status line and the
   install lines (also in the example for GitHub Actions) in the same pull request.
3. After it is merged, tag the merge commit and push the tag:

   ```bash
   git switch main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. The workflow builds the package and checks that the tag, `pyproject.toml` and `CHANGELOG.md`
   agree; installs the wheel and the sdist, each into a clean environment, and runs them on a
   project; and then waits for the approval of the `pypi` environment. Approve it in the run's page.
5. After the publication, the workflow makes the **GitHub release** (the job `github-release`, the
   only one that may write to the repository): its notes are the paragraph, the sections of the
   entry of the version in `CHANGELOG.md`, the install line and the links to the changelog and to
   the comparison with the previous tag; the wheel and the sdist that were published are attached;
   a version with letters in it (`0.3.0rc1`) is a pre-release. If that job fails, nothing is
   undone: make the release by hand with the same script,

   ```bash
   python3 .github/scripts/release_notes.py X.Y.Z --previous W.X.Y > notes.md
   gh release create vX.Y.Z --verify-tag --title X.Y.Z --notes-file notes.md --latest
   ```

6. Check <https://pypi.org/project/dbt-macro-test/> and the release page, and install it into a new
   environment.

## What the workflow checks

- the tag is `v` plus the version in `pyproject.toml`, and `CHANGELOG.md` has a heading for it and,
  under it, the paragraph that says what the version is for (not for a `.dev` dry run);
- `twine check --strict` passes, and the wheel holds `py.typed` and `LICENSE`, the sdist `LICENSE`;
- the wheel and the sdist each install into a new environment, `dbt-macro-test` is the installed
  one (not the checkout), and `dbt-macro-test run` passes on the project in `tests/fixtures/project`.
