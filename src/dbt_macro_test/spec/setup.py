import json
import math
import re
from dataclasses import dataclass
from typing import Any

# What a model logs for each relation it makes, followed by that relation as JSON, so that the tool
# can drop it afterwards.
RELATION_MARK = "__dmt_relation__"

_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SetupRelation:
    """A relation that a case needs before the macro runs, made by the tool as a temporary one.

    It is filled by `rows` (a list of mappings) or by `sql` (a select), the author's own.
    """

    name: str
    rows: tuple[dict[str, Any], ...] | None = None
    sql: str | None = None

    def select_sql(self) -> str:
        """The select that fills the relation. It is rendered as Jinja when the model is, so it
        may name the relations made before it, `{{ relations.<name> }}`."""
        if self.rows is not None:
            return rows_to_select(self.rows)
        assert self.sql is not None, "a relation is filled by rows or by sql"
        return self.sql.strip()


def sql_value(value: Any) -> str:
    """One value of a row as SQL, in a form every warehouse reads the same way: a number, a
    boolean or null as they are, a string quoted by dbt's own macro, which each adapter may
    override, and so not by this tool."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"cannot write {value!r} in SQL")
        return repr(value)
    if isinstance(value, str):
        return "'{{ dbt.escape_single_quotes(" + json.dumps(value) + ") }}'"
    raise TypeError(f"cannot write a {type(value).__name__} in rows; use `sql` for it")


def rows_to_select(rows: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> str:
    """A select that returns the rows: `select 1 as id, 'a' as v union all select 2, 'b'`."""
    columns = list(rows[0])
    for column in columns:
        if not isinstance(column, str) or not _COLUMN.match(column):
            raise ValueError(f"{column!r} is not a column name (letters, digits, _)")
    selects = []
    for i, row in enumerate(rows):
        if list(row) != columns:
            raise ValueError(f"row {i} has the columns {list(row)}, not {columns}")
        if i == 0:
            selects.append("select " + ", ".join(f"{sql_value(row[c])} as {c}" for c in columns))
        else:
            selects.append("select " + ", ".join(sql_value(row[c]) for c in columns))
    return "\nunion all\n".join(selects)
