"""The notes of a GitHub release, made from the entry of the version in CHANGELOG.md (#122).

    python3 .github/scripts/release_notes.py 0.3.0 --previous 0.2.0 --repo OWNER/REPO > notes.md

The entry is `## [0.3.0] - date`, then the **highlights** (what the version is for: the text before
the first `###`), then the `###` sections. The notes are the highlights, the sections as they are,
the install line, and the links to the changelog and to the comparison with the previous version.
A version without an entry, or an entry without highlights, is an error, which is what stops a
release that has none before it is published. Only the standard library is used.
"""

import argparse
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
PACKAGE = "dbt-macro-test"


class NotesError(Exception):
    """The changelog cannot give the notes of a version."""


def entry(changelog: str, version: str) -> str:
    """The text of `## [version] - ...` up to the next `## [`, without the heading line."""
    heading = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n", changelog, re.M)
    if heading is None:
        raise NotesError(f"CHANGELOG.md has no heading '## [{version}]'")
    rest = changelog[heading.end() :]
    following = re.search(r"^## \[", rest, re.M)
    return (rest[: following.start()] if following else rest).strip("\n")


def split_entry(text: str) -> tuple[str, str]:
    """The highlights (before the first `###`) and the sections (from it)."""
    first = re.search(r"^### ", text, re.M)
    if first is None:
        return text.strip(), ""
    return text[: first.start()].strip(), text[first.start() :].strip()


def notes(changelog: str, version: str, previous: str | None, repo: str) -> str:
    highlights, sections = split_entry(entry(changelog, version))
    if not highlights:
        raise NotesError(
            f"the entry of {version} in CHANGELOG.md has no highlights: write a paragraph under "
            f"its heading, before the first '###', that says what the version is for"
        )
    base = f"https://github.com/{repo}"
    parts = [highlights]
    if sections:
        parts += ["## Changes", sections]
    parts += ["## Install", f"```bash\npip install -U {PACKAGE}=={version}\n```"]
    links = [f"[CHANGELOG]({base}/blob/v{version}/CHANGELOG.md)"]
    if previous:
        links.append(f"[v{previous}...v{version}]({base}/compare/v{previous}...v{version})")
    parts.append("Full list of changes: " + " · ".join(links))
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("version", help="for example 0.3.0, without the v")
    parser.add_argument("--previous", help="the previous version, for the link to the comparison")
    parser.add_argument("--repo", default="HirofumiTsuda/dbt-macro-test")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    args = parser.parse_args(argv)
    try:
        text = notes(args.changelog.read_text(), args.version, args.previous, args.repo)
    except NotesError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
