import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# What a model logs for each relation it makes, followed by that relation as JSON, so that the tool
# can drop it afterwards.
RELATION_MARK = "__dmt_relation__"

_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SetupRelation:
    """A relation that a case needs before the macro runs, made by the tool.

    It is filled by `rows` (a list of mappings) or by `sql` (a select), the author's own. It is
    temporary unless `temporary` is false: what each is is the adapter's to say (dbt's
    `create_table_as` takes the boolean, and the adapter chooses the kind of relation).
    """

    name: str
    rows: tuple[dict[str, Any], ...] | None = None
    sql: str | None = None
    temporary: bool = True

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


def plain_value(value: Any) -> str:
    """One value of a row as SQL, written without Jinja or dbt's macros, which are not there where
    an input of a unit test is read. A number, a boolean or null as they are; a string only when
    quoting it is the same on every warehouse, that is, when it has no quote, backslash or Jinja."""
    if isinstance(value, str):
        bad = [c for c in ("'", "\\", "{{", "{%", "{#") if c in value]
        if bad:
            raise ValueError(
                f"cannot write {value!r} in rows, since it has {bad[0]!r} and how to quote that "
                "differs between warehouses; use `sql` for it"
            )
        return f"'{value}'"
    if value is None or isinstance(value, bool | int | float):
        return sql_value(value)
    raise TypeError(f"cannot write a {type(value).__name__} in rows; use `sql` for it")


def rows_to_select(
    rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    value_sql: Callable[[Any], str] = sql_value,
) -> str:
    """A select that returns the rows: `select 1 as id, 'a' as v union all select 2, 'b'`.

    `value_sql` writes one value; the default quotes a string with dbt's own macro."""
    columns = list(rows[0])
    for column in columns:
        if not isinstance(column, str) or not _COLUMN.match(column):
            raise ValueError(f"{column!r} is not a column name (letters, digits, _)")
    selects = []
    for i, row in enumerate(rows):
        if list(row) != columns:
            raise ValueError(f"row {i} has the columns {list(row)}, not {columns}")
        if i == 0:
            selects.append("select " + ", ".join(f"{value_sql(row[c])} as {c}" for c in columns))
        else:
            selects.append("select " + ", ".join(value_sql(row[c]) for c in columns))
    return "\nunion all\n".join(selects)
