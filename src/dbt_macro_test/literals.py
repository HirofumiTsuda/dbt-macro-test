import json
import math
from typing import Any


def to_jinja_literal(value: Any) -> str:
    """Render a YAML value as a Jinja literal, for use as a macro argument."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"cannot render {value!r} as a Jinja literal")
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(to_jinja_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        items = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"mapping key {key!r} is not a string")
            items.append(f"{json.dumps(key)}: {to_jinja_literal(item)}")
        return "{" + ", ".join(items) + "}"
    raise TypeError(f"cannot render a {type(value).__name__} as a Jinja literal")
