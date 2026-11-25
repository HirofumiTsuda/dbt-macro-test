---
name: record-demo
description: Re-record the demo animation of the README (docs/images/demo.gif), a real session of the quick start recorded with asciinema and converted to a GIF with agg. Use when the output of `dbt-macro-test run` or the quick start changes, or when asked to re-record, update or redo the demo GIF or animation.
---

# Record the demo

`docs/images/demo.gif` is a **recording of a real session**, not a drawing: the quick start of the
README, run for real with the current code. Never hand-draw it or edit frames; if the output of the
tool changed, record again. Write the pull request in English and follow the `create-pr` skill
(the issue first, `[#N]` in the title).

## When

The output of `dbt-macro-test run` changes (its lines, its summary, the failure), the quick start
changes (the macro, the spec, the commands), or the GIF is found wrong. Not for a change that does
not show on the screen.

## What is needed

- `uv` (for `uvx asciinema`), and the font DejaVu Sans Mono (`fc-list | grep DejaVu`).
- `agg`, the converter of asciinema, as an **executable fetched from GitHub**. Running a fetched
  executable needs the user's agreement: **ask first**, and when it is refused, stop and say what
  was refused and why it is needed (see below); do not look for a way round.
  - Version 1.9.0 was used (`gh release download v1.9.0 -R asciinema/agg -p
    agg-x86_64-unknown-linux-gnu -O agg`, in a directory of its own, not in the repository).
  - **Check it before running it**: compare `sha256sum agg` with the digest GitHub publishes,
    `gh api repos/asciinema/agg/releases/tags/v1.9.0 --jq '.assets[] | select(.name ==
    "agg-x86_64-unknown-linux-gnu") | .digest'`. They must be the same (`f111e315…aeda6` for 1.9.0).
    Then `chmod +x`.
  - Another version, or another platform: check the digest the same way, and say it in
    `docs/images/README.md`.

## Steps

1. **A scratch directory** outside the repository (the scratchpad), with a `shop/` project that is
   exactly the quick start of the README: `dbt_project.yml` (name `shop`, profile `shop`,
   `macro-paths: ["macros"]`), `profiles.yml` (duckdb, `path: ":memory:"`), `macros/safe_divide.sql`
   and `macro_test/safe_divide.yml` with the two cases of the README. If the quick start changed,
   change this the same way: the GIF must show what the README says.
2. **`bin/dbt-macro-test`**, a two-line shell script that `exec`s the checkout's
   `.venv/bin/dbt-macro-test "$@"`, so that the recording runs the code of the branch, and
   `demo.sh` from `docs/images/demo.sh` next to `shop/` and `bin/`. The script types each command
   and then runs it for real; the second run is made to fail by a real `sed` on the spec.
3. **Record**, wide enough that no line wraps (the longest line of dbt's output is about 120
   characters) and tall enough for one run:

   ```bash
   TERM=xterm-256color uvx asciinema rec --overwrite -q --cols 122 --rows 38 \
     -c "bash $PWD/demo.sh" run.cast
   ```

4. **The script changes the spec** (`2.5` to `2.0`) and does not change it back. Restore it before
   the next recording (`sed -i 's/{result: 2.0}/{result: 2.5}/' shop/macro_test/safe_divide.yml`),
   and delete `shop/target` and `shop/logs`, or the first run will not be the first.
5. **Convert**:

   ```bash
   agg --theme github-dark --font-family "DejaVu Sans Mono" --font-size 14 \
       --idle-time-limit 2 --last-frame-duration 4 run.cast run.gif
   ```

   Its progress bar is noisy: `2>&1 | tr '\r' '\n' | tail -1`. Expect about 160 KB and about 18 s.
6. **Look at it.** The size of the file says nothing. Take frames with Pillow (`uvx --with pillow
   python`) and open them with the Read tool. The frames are not evenly spaced in time (idle time
   is cut), so pick them **by time**, summing the `duration` of each frame, not by index. Look at
   three: the passing run, the typing of the `sed`, the failing run with its diff. Check that
   - no line wraps, and each run fits on one screen (the top of the second is not scrolled out);
   - the green of PASS and the red of FAIL and of the diff are there;
   - the text is the real output (version of dbt, `PASS=2` and `1 failed, 1 passed`, exit code 1).
   If not, change `--cols`, `--rows` or `--font-size` and record again.
7. **Put it in the repository**: `run.gif` and `run.cast` become `docs/images/demo.gif` and
   `docs/images/demo.cast`; `demo.sh` stays in `docs/images/`. In `docs/images/README.md` update the
   versions (asciinema, agg and its SHA-256, dbt-core, dbt-duckdb) if they changed.
8. **The README refers to the GIF by its address on `main`**
   (`https://raw.githubusercontent.com/HirofumiTsuda/dbt-macro-test/main/docs/images/demo.gif`),
   because PyPI shows the README as the page and cannot read a relative path. So the image does not
   show in the README of the pull request before the merge. After the merge, check that the address
   answers with `Content-Type: image/gif`. Say in the pull request that this is not checked before.

## Written in the pull request

That it is a real session (and which versions), that the frames were looked at and what was fixed,
that `agg` was fetched with the user's agreement and its SHA-256 matched the published one, and
what is not checked (how it shows on GitHub and on PyPI).

## Why it asks first

A fetched executable is outside what the repository and PyPI vouch for. The first time, running it
was refused; the user then agreed to it for this purpose. That agreement is for this converter, at
the version whose digest was checked, not for fetched executables in general.
