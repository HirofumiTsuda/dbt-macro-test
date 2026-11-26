---
name: record-demo
description: Re-record the demo animation of the README (docs/images/demo.gif), a real session of the sample project recorded with asciinema and converted to a GIF with agg. Use when the output of `dbt-macro-test run` or the sample project changes, or when asked to re-record, update or redo the demo GIF or animation.
---

# Record the demo

`docs/images/demo.gif` is a **recording of a real session**, not a drawing: the sample project, run
for real with the current code. Never hand-draw it or edit frames; if the output of the
tool changed, record again. Write the pull request in English and follow the `create-pr` skill
(the issue first, `[#N]` in the title).

## When

The output of `dbt-macro-test run` changes (its lines, its summary, the failure), the sample
project changes in a way that shows (its cases), or the GIF is found wrong. Not for a change that does
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

1. **A scratch directory** outside the repository, with a copy of `dev/sample_project` as `shop/`
   (without its `target/` and `logs/`): the recording runs the sample, so what it shows is what the
   README says the sample has. If the sample changes (more cases, other names), look at the frames:
   a line that is longer than the `--cols` wraps.
2. **`bin/dbt-macro-test`**, a two-line shell script that `exec`s the checkout's
   `.venv/bin/dbt-macro-test "$@"`, so that the recording runs the code of the branch, and
   `demo.sh` from `docs/images/demo.sh` next to `shop/` and `bin/`. The script types each command
   and then runs it for real; the last run is made to fail by a real `sed` on a spec of the sample.
3. **Record**, wide enough that no line wraps (the longest line of dbt's output is about 120
   characters) and tall enough for one run:

   ```bash
   TERM=xterm-256color uvx asciinema rec --overwrite -q --cols 122 --rows 38 \
     -c "bash $PWD/demo.sh" run.cast
   ```

4. **The script changes a spec** (`2.5` to `2.0` in `macro_test/expressions.yml`) and does not change
   it back. Make `shop/` again from the sample before the next recording, and without `target` and
   `logs`, or the first run will not be the first.
5. **Convert**:

   ```bash
   agg --theme github-dark --font-family "DejaVu Sans Mono" --font-size 14 \
       --idle-time-limit 2 --last-frame-duration 4 run.cast run.gif
   ```

   Its progress bar is noisy: `2>&1 | tr '\r' '\n' | tail -1`. Expect about 160 KB and about 18 s.
6. **Look at it.** The size of the file says nothing. Take frames with Pillow (`uvx --with pillow
   python`) and open them with the Read tool. The frames are not evenly spaced in time (idle time
   is cut), so pick them **by time**, summing the `duration` of each frame, not by index. Look at
   three: the list of the cases, the end of the full run, the failing run with its diff (also the
   **last frame**: `social-preview.png` is cut out of it, so run `make_social_preview.py` again and
   look at that image too). Check that
   - no line wraps, and each run fits on one screen (the top of the second is not scrolled out);
   - the green of PASS and the red of FAIL and of the diff are there;
   - the text is the real output (version of dbt, `26 passed`, and `1 failed` with exit code 1).
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
