# The demo of the README

`demo.gif` is the animation at the top of the README. It is a recording of a real session, not a
drawing: `demo.sh` types each command on the screen and then runs it for real, in the project of the
quick start (a dbt project with a duckdb profile, the macro `safe_divide`, and its spec). The second
run fails because the script changes one expected value with `sed`.

| File | What it is |
|---|---|
| `demo.sh` | The script that was recorded (it expects the quick-start project in `shop/` next to it) |
| `demo.cast` | The recording, in asciinema's format; `uvx asciinema play docs/images/demo.cast` replays it |
| `demo.gif` | `demo.cast` converted to a GIF |
| `social-preview.png` | The image GitHub shows when the repository is linked (1280x640). It is uploaded by hand: Settings, General, Social preview; GitHub has no API for it |
| `overview.svg` | The overview figure of the README ("How it works"), as an editable SVG |
| `overview.png` | `overview.svg` rendered at 2400 px wide, which is what the README shows |
| `make_social_preview.py` | Makes `social-preview.png` (`uvx --with pillow python docs/images/make_social_preview.py`) |

`social-preview.png` is not drawn either: the terminal in it is cut out of the last frame of
`demo.gif` (the error with dbt's diff, and the summary with the exit code, two pieces of the real
frame, with nothing typed or edited); only the tagline and the install command next to it are text.
When `demo.gif` is made again, make this image again too.

To make it again, the steps are in the skill `.claude/skills/record-demo/SKILL.md` (for Claude, with what to check
in the frames). By hand, with the project in `shop/` next to `demo.sh` and `dbt-macro-test` on the `PATH`:

```bash
uvx asciinema rec --overwrite -q --cols 122 --rows 38 -c "bash demo.sh" demo.cast
agg --theme github-dark --font-family "DejaVu Sans Mono" --font-size 14 \
    --idle-time-limit 2 --last-frame-duration 4 demo.cast demo.gif
```

Made with asciinema 2.4.0 and [agg](https://github.com/asciinema/agg) 1.9.0 (the Linux x86_64
binary of the release, checked against the SHA-256 that GitHub publishes for it,
`f111e315cd71056b116302342553dd765b7297579ed511f111d0cedb442aeda6`), with dbt-core 1.12.5 and
dbt-duckdb 1.11.0. The times in the output are those of the day it was recorded.

The README refers to the GIF by its address on `main`, since PyPI, which shows the README as the
page, cannot read an image by a relative path. If the file is renamed or moved, change that address.

`overview.png` is made from `overview.svg` with CairoSVG, from the root of the repository, and
needs the font DejaVu Sans (and Mono) to look as it does:

```bash
uvx --with cairosvg python -c "import cairosvg; cairosvg.svg2png(url='docs/images/overview.svg', write_to='docs/images/overview.png', output_width=2400)"
```

Every box and arrow of the figure is something the code does: the spec and the check of the
arguments (`spec/`, `engine/validate.py`), the generated project (`project/generate.py`,
`spec/output.py`), the cases that run alone (`split_isolated` in `spec/select.py`), dbt run
in the process by `engine/runner.py`, and the report and the exit codes (`cli.py`). When one of
them changes, change the figure.
