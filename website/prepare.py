"""Writes src/content/docs (what Starlight reads) from the Markdown of the repository.

The sources stay plain Markdown that reads on GitHub: the pages of docs/, the README, the changelog.
This script, run before every build,

- takes the title of a page from its first `# heading`, as Starlight wants it in the front matter;
- fills `<!-- include: FILE [section] -->` with the text of FILE (the part between the markers
  `<!-- --8<-- [start:section] -->` and `<!-- --8<-- [end:section] -->`, if a section is named),
  so that the quick start and the changelog are written once;
- turns a relative link to another page of docs/ into the address of that page on the site (with
  the base path, so that the links validator checks it), and a
  relative link to anything else in the repository (the README, the sample project) into its
  address on GitHub;
- copies the images the pages show.

Nothing but the standard library. Run it from anywhere: `python3 website/prepare.py`.
"""

import os
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCS = ROOT / "docs"
OUT = HERE / "src" / "content" / "docs"
BASE = os.environ.get("BASE_PATH", "/dbt-macro-test").rstrip("/")
GITHUB = "https://github.com/HirofumiTsuda/dbt-macro-test"

# (source, route): the pages of the site. The route is the path under the base, without a slash
PAGES = {
    HERE / "content" / "index.md": "",
    HERE / "content" / "changelog.md": "changelog",
    DOCS / "guide.md": "guide",
    DOCS / "spec.md": "spec",
    DOCS / "design.md": "design",
    DOCS / "releasing.md": "releasing",
    DOCS / "history" / "design-log.md": "history/design-log",
}
IMAGES = [DOCS / "images" / "demo.gif", DOCS / "images" / "overview.png"]

INCLUDE = re.compile(r"<!-- include: (\S+)(?: (\S+))? -->")
LINK = re.compile(r"(?<!!)(\[[^\]]*\])\(([^)\s]+)\)")


def included(match: re.Match[str]) -> str:
    text = (ROOT / match.group(1)).read_text()
    section = match.group(2)
    if section:
        start = f"<!-- --8<-- [start:{section}] -->"
        end = f"<!-- --8<-- [end:{section}] -->"
        text = text.split(start, 1)[1].split(end, 1)[0]
    else:
        text = re.sub(r"\A# [^\n]*\n+", "", text)  # the page has its own title
    return text.strip("\n")


def route_of(source: Path) -> str | None:
    """The route of the page that `source` (a Markdown file of the repository) becomes, if any."""
    for page, route in PAGES.items():
        # a page written for the site only (home, changelog) is linked to as if it were in docs/
        address = DOCS / page.name if page.parent == HERE / "content" else page
        if address.resolve() == source.resolve():
            return route
    return None


def rewrite(target: str, source: Path, route: str) -> str:
    """One link target of the page written from `source`, which will be at `route`."""
    if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target):
        return target
    path, _, anchor = target.partition("#")
    resolved = Path(os.path.normpath(source.parent / path))
    suffix = f"#{anchor}" if anchor else ""
    page = route_of(resolved)
    if page is not None:
        # with the base, so that the links validator can check the page and the heading
        return f"{BASE}/{page}/{suffix}" if page else f"{BASE}/{suffix}"
    if not resolved.exists():
        where = source.relative_to(ROOT)
        raise SystemExit(f"{where}: the link '{target}' goes to {resolved}, which is not there")
    inside = resolved.relative_to(ROOT).as_posix()
    kind = "tree" if resolved.is_dir() else "blob"
    return f"{GITHUB}/{kind}/main/{inside}{suffix}"


def build(source: Path, route: str) -> str:
    text = INCLUDE.sub(included, source.read_text())
    heading = re.match(r"# ([^\n]+)\n+", text)
    if heading is None:
        raise SystemExit(f"{source}: the page has to start with a # heading")
    title = heading.group(1).strip()
    body = text[heading.end() :]
    body = body.replace("__BASE__", BASE)
    # the pages written for the site only (home, changelog) link as if they were in docs/
    where = DOCS / source.name if source.parent == HERE / "content" else source
    body = LINK.sub(lambda m: f"{m.group(1)}({rewrite(m.group(2), where, route)})", body)
    escaped = title.replace('"', '\\"')
    return f'---\ntitle: "{escaped}"\n---\n\n{body.rstrip()}\n'


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    for source, route in PAGES.items():
        target = OUT / ((route or "index") + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build(source, route))
    public = HERE / "public" / "images"
    public.mkdir(parents=True, exist_ok=True)
    for image in IMAGES:
        shutil.copy(image, public / image.name)
    print(f"wrote {len(PAGES)} pages to {OUT.relative_to(ROOT)} (base '{BASE}')")


if __name__ == "__main__":
    main()
