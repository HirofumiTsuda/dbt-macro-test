import re
from dataclasses import dataclass
from typing import Any

from dbt_macro_test.spec.setup import plain_value, rows_to_select

_NAME = r"""(?:'([^']+)'|"([^"]+)")"""
_REFERENCE = re.compile(rf"^\s*(ref|source)\(\s*{_NAME}\s*(?:,\s*{_NAME}\s*)?\)\s*$")


@dataclass(frozen=True)
class GivenInput:
    """A `ref` or a `source` that a macro calls, with the rows the macro is to see in it.

    The rows are all the data there is: the tool writes a stand-in for the node, which is never
    built, and hands the rows to dbt as a select (`format: sql`), since for rows written as
    mappings dbt asks the warehouse for the columns of the relation, which the stand-in is not.
    """

    kind: str  # "ref" or "source"
    names: tuple[str, ...]  # ("orders",) or ("shop", "orders")
    rows: tuple[dict[str, Any], ...] | None = None
    sql: str | None = None

    @property
    def reference(self) -> str:
        """The input as dbt's unit tests name it: `ref('orders')`, `source('shop', 'orders')`."""
        return f"{self.kind}({', '.join(repr(n) for n in self.names)})"

    def select_sql(self) -> str:
        if self.rows is not None:
            return rows_to_select(self.rows, plain_value)
        assert self.sql is not None, "an input is given by rows or by sql"
        return self.sql.strip()

    def unit_test_input(self) -> dict[str, str]:
        """The entry for the `given` of the unit test."""
        return {"input": self.reference, "format": "sql", "rows": self.select_sql()}


def parse_reference(text: str) -> tuple[str, tuple[str, ...]]:
    """`ref('orders')` as ("ref", ("orders",)), `source('a', 'b')` as ("source", ("a", "b")).

    Raises ValueError for anything else, and for a `ref` of a package's model or a `source` with
    one name, which the tool does not stand in for.
    """
    match = _REFERENCE.match(text)
    if match is None:
        raise ValueError(f"{text!r} is not ref('model') or source('source', 'table')")
    kind = match.group(1)
    names = tuple(
        n for n in (match.group(2) or match.group(3), match.group(4) or match.group(5)) if n
    )
    if kind == "ref" and len(names) != 1:
        raise ValueError("a ref with a package is not supported; give ref('model')")
    if kind == "source" and len(names) != 2:
        raise ValueError("a source needs its name and its table: source('source', 'table')")
    return kind, names
