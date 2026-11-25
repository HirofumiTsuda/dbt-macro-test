from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import jinja2
from dbt_common.clients import jinja as jinja_common
from dbt_common.exceptions import CompilationError
from jinja2 import nodes

_ENVIRONMENT = jinja2.Environment(extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"])


@dataclass(frozen=True)
class Signature:
    required: list[str]
    optional: list[str]
    accepts_any_name: bool

    @property
    def names(self) -> list[str]:
        return [*self.required, *self.optional]


def signatures_in(source: str) -> dict[str, Signature]:
    """The signature of every macro defined in a piece of Jinja source."""
    found: dict[str, Signature] = {}
    blocks = jinja_common.extract_toplevel_blocks(
        source, allowed_blocks={"macro"}, collect_raw_data=False
    )
    for block in blocks:
        if not isinstance(block, jinja_common.BlockTag) or block.full_block is None:
            continue
        for macro in _ENVIRONMENT.parse(block.full_block).find_all(nodes.Macro):
            names = [arg.name for arg in macro.args]
            split = len(names) - len(macro.defaults)
            referenced = {name.name for name in macro.find_all(nodes.Name)}
            found[macro.name] = Signature(
                required=names[:split],
                optional=names[split:],
                accepts_any_name="kwargs" in referenced,
            )
    return found


def find_signatures(macro_dirs: Collection[Path]) -> dict[str, list[Signature]]:
    """Every definition of every macro under the given directories, by macro name.

    A file that cannot be read or parsed is skipped: dbt reports that itself
    when it runs, and a macro that cannot be found is simply not checked.
    """
    found: dict[str, list[Signature]] = {}
    for directory in macro_dirs:
        for path in sorted(directory.rglob("*.sql")):
            try:
                signatures = signatures_in(path.read_text())
            except (OSError, UnicodeDecodeError, jinja2.TemplateSyntaxError, CompilationError):
                continue
            for name, signature in signatures.items():
                found.setdefault(name, []).append(signature)
    return found


def problems_with(signature: Signature, given: Collection[str]) -> list[str]:
    """What is wrong with passing these argument names to a macro, if anything."""
    problems = []
    if not signature.accepts_any_name:
        unknown = [name for name in given if name not in signature.names]
        for name in unknown:
            problems.append(f"unknown argument {name!r} (the macro takes: {_listed(signature)})")
    for name in signature.required:
        if name not in given:
            problems.append(f"missing argument {name!r}, which has no default")
    return problems


def _listed(signature: Signature) -> str:
    return ", ".join(signature.names) if signature.names else "no arguments"
