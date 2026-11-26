---
name: release
description: Prepare and carry out a release of dbt-macro-test to PyPI, or a dry run on TestPyPI. Use when the user asks to release, cut or publish a version, tag a release, or do a TestPyPI dry run. It lists what Claude may do alone and what only the user decides.
---

# Release

`docs/releasing.md` has the steps for a person; read it first, and change both when the way
changes. This skill adds what Claude must check and what Claude must not do alone. The workflow is
`.github/workflows/release.yml`.

## What only the user decides

A version on PyPI, and on TestPyPI, **can never be used again**, even if the release is deleted.
So Claude does none of these on its own, and does each only when the user has just said to:

- push a tag `vX.Y.Z` (it starts the release);
- run the workflow by hand (`gh workflow run release.yml`), which publishes to TestPyPI;
- approve the `pypi` environment (that is the user's approval, in the browser);
- change the settings of PyPI, TestPyPI or the environments of GitHub (the user's accounts; Claude
  may create the environments with `gh api` only when asked).

Everything else (the release pull request, the checks, the verification after) Claude does, and
reports in Japanese, short, with what was not checked.

## Before anything: look

1. `main` is green, and nothing is open that the release depends on (`gh api
   "repos/HirofumiTsuda/dbt-macro-test/issues?state=open"`; the roadmap is #17, the release is #12
   and #56).
2. **The version.** Semantic versioning; before 1.0.0 a minor version may change the spec format.
   Say what was chosen and why. Ask when it is not obvious.
3. **The changelog is true.** Read each line of the entry of the version in `CHANGELOG.md` and check
   it against the code or by running it (the README says the same about the spec: nothing is said
   that was not run). Changes since the last tag: `git log <last tag>..main`, and what the closed
   issues said.
4. **The README and `docs/` say what is so.** Run the quick start of the README from nothing
   (a new project, a new venv) and compare its output with what the README shows. The links that
   leave the README are absolute (PyPI cannot read a relative path).
5. `uv build` and `uvx twine check --strict dist/*` pass. The classifiers are in the official list
   (`uvx --from trove-classifiers python`, compare `pyproject.toml` with `trove_classifiers.classifiers`):
   PyPI refuses an upload with one it does not know, and `twine check` does not look.

## The first release only: the README says "not on PyPI"

The page of a release on PyPI is the README **as it was when the version was built**, and cannot be
changed afterwards except by a new version. The README of the first release says it is not on PyPI,
not released yet, and installs from `git+https://...`; that would be on the PyPI page of 0.1.0. So,
in the release pull request:

- the Status line ("not released yet", "not on PyPI") is changed to what is true then;
- the install line becomes `pip install dbt-macro-test` (with the adapter), here and in the example
  for GitHub Actions of the README; **that has never been run against PyPI**, so it is checked
  after the publication, and the example's workflow is run again once;
- the demo animation and the links need no change.

Ask the user about the wording of the Status line, and say that the install line cannot be tried
before the package is on PyPI (so the first minutes after the publication are when it is checked).

## The `pypi` environment must exist, with a reviewer, before any tag

**This is what makes "waits for the approval" true.** If the job names an environment that does not
exist, GitHub creates it on the first run **with no protection**, and the job goes on at once; the
trusted publisher on PyPI would accept it, and the version would be published without anyone
approving it. (The environment `testpypi` was made that way by the first dry run, and has no rule.)
So, before asking for or pushing a tag, run

```bash
gh api repos/HirofumiTsuda/dbt-macro-test/environments --jq '.environments[] | {name, reviewers: [.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[]?.reviewer.login]}'
```

and do not go on unless `pypi` is there with the user as a reviewer. When it is not (it was not,
on 2026-11-25), say so, and **ask** before creating it: the user, as reviewer, is the approval.

## Settings, once (the user's)

Pending trusted publishers on PyPI and TestPyPI (project `dbt-macro-test`, owner `HirofumiTsuda`,
repository `dbt-macro-test`, workflow `release.yml`, environment `pypi` and `testpypi`), and the
GitHub environments `pypi` (with the user as a required reviewer) and `testpypi`. Both publishers
were set on 2026-11-25; check that the environment `pypi` exists with a reviewer before the tag
(`gh api repos/HirofumiTsuda/dbt-macro-test/environments`), and **ask** before creating it.

## A dry run on TestPyPI

Worth doing when `pyproject.toml`, the workflow or the README changed since the last one: it shows
what PyPI does with the package. Done twice (0.1.0.dev1: the whole workflow; 0.1.0.dev2: the page
of the README).

1. On a throwaway branch from `main`: `version = "X.Y.Z.devN"` in `pyproject.toml`, and a heading
   `## [X.Y.Z.devN] - dry run on TestPyPI, not a release` in `CHANGELOG.md` (the workflow checks it).
   Check that TestPyPI does not have the version: `curl -s -o /dev/null -w '%{http_code}'
   https://test.pypi.org/pypi/dbt-macro-test/X.Y.Z.devN/json` must be 404.
2. **Ask the user**, then `gh workflow run release.yml --ref <branch>`, and wait for the run
   (`gh run view <id> --json conclusion,jobs`). `build`, both `smoke` jobs and `testpypi` pass;
   `pypi` is skipped.
3. Check what was registered, with the JSON API
   (`https://test.pypi.org/pypi/dbt-macro-test/X.Y.Z.devN/json`): the description, its content type,
   the project URLs, the classifiers, the keywords. **The page itself answers a script with a
   bot-challenge page**, so it cannot be read: render the description with
   `uvx --from "readme-renderer[md]" python` (`readme_renderer.markdown.render`), which is what PyPI
   uses, and list the images and the links that survive. Then **ask the user to open the page**
   (`https://test.pypi.org/project/dbt-macro-test/X.Y.Z.devN/`) and look.
4. Delete the branch (local and remote). The version stays on TestPyPI for good; say so.
5. Install it into a new environment and run the fixture project:
   `pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/
   dbt-macro-test==X.Y.Z.devN` (and `dbt-duckdb` from PyPI), `dbt-macro-test --help`, and
   `dbt-macro-test run` on a copy of `tests/fixtures/project` (27 passed, 1 skipped).

## The release

1. **The release pull request**, with its issue (`[#N]`, see `create-pr`): `version` in
   `pyproject.toml` if it is not already, the heading of the version in `CHANGELOG.md` renamed to
   `## [X.Y.Z] - YYYY-MM-DD` (today, from `date +%F`; do not guess the date), **a paragraph under it
   that says what the version is for** (the head of the GitHub release; the build stops without it),
   what changed listed,
   and the README changes of the section above for the first release. Its checks include the build
   and the smoke test of the release workflow (it runs for a change to `pyproject.toml` or
   `CHANGELOG.md`). In the body, **no "close(s)/fix(es) #N" unless it should close that issue**:
   GitHub reads it even in a negation (this closed #56 and #71 by mistake).
2. Merge it only when the user says so. Update local `main`.
3. **Ask the user** to tag, or, when they say to, `git tag vX.Y.Z` on the merge commit and
   `git push origin vX.Y.Z`. The workflow starts. (The pattern `v[0-9]+.[0-9]+.[0-9]+*` has not met
   a tag yet: if no run starts, look at the pattern first.)
4. The workflow builds, checks that the tag, the version and the changelog agree, installs the wheel
   and the sdist into clean environments and runs them, and then **waits for the approval of
   `pypi`**. Tell the user it is waiting, and what they approve. Claude does not approve.
5. After the publication, check, and report what was and was not checked:
   - `https://pypi.org/pypi/dbt-macro-test/X.Y.Z/json` answers, with the right metadata; and the
     page (**ask the user to look**; a script cannot read it);
   - a new environment: `pip install dbt-duckdb dbt-macro-test==X.Y.Z`, `dbt-macro-test --help`, the
     quick start of the README **as it is written now** (this is the first time its install line is
     run against PyPI), and `run` on a copy of `tests/fixtures/project`;
   - for the first release, the example workflow of the README, run once on GitHub (a throwaway pull
     request that is closed afterwards).
   - the GitHub release was made by the workflow (the job `github-release`): read its page, the
     notes and the two files; if the job failed, nothing is undone, and the release is made by hand
     as `docs/releasing.md` says;
6. Close what the release finishes (#56, then #12), tick the roadmap (#17), and write in the issue
   what was published and what was checked. If something is wrong with the published version, it
   cannot be replaced: say so, and prepare the next version (a yanked release is the user's call).

## Written to the user

Short, in Japanese: what was done, what is left for them (the tag, the approval, looking at the
page), and what was not checked (the page of PyPI, an adapter other than duckdb, macOS).
