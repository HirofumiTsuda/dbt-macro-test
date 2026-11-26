from enum import Enum


class Output(Enum):
    """What a macro's output is, which decides how the throwaway model wraps it.

    `expression`, `columns` and `query` are SQL that the warehouse evaluates. `text` is not: it is
    returned as one string, which dbt's unit test compares as it is. `{call}` in a template is the
    call of the macro.
    """

    EXPRESSION = ("expression", "select {{{{ {call} }}}} as result\n")
    COLUMNS = ("columns", "select {{{{ {call} }}}}\n")
    QUERY = ("query", "{{{{ {call} }}}}\n")
    # The blank space at either end of what a macro returns comes from how its block is written, so
    # it is dropped; the quotes are escaped by dbt's own macro, which each adapter may override.
    TEXT = ("text", "select '{{{{ dbt.escape_single_quotes(({call}) | trim) }}}}' as result\n")

    label: str
    template: str

    def __init__(self, label: str, template: str) -> None:
        self.label = label
        self.template = template

    @classmethod
    def parse(cls, label: object) -> "Output":
        for member in cls:
            if member.label == label:
                return member
        allowed = ", ".join(member.label for member in cls)
        raise ValueError(f"{label!r} is not one of: {allowed}")

    def model_sql(self, call: str) -> str:
        return self.template.format(call=call)
