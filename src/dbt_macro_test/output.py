from enum import Enum


class Output(Enum):
    """What a macro's output is, which decides how the throwaway model wraps it."""

    EXPRESSION = ("expression", "select ", " as result")
    COLUMNS = ("columns", "select ", "")

    label: str
    before: str
    after: str

    def __init__(self, label: str, before: str, after: str) -> None:
        self.label = label
        self.before = before
        self.after = after

    @classmethod
    def parse(cls, label: object) -> "Output":
        for member in cls:
            if member.label == label:
                return member
        allowed = ", ".join(member.label for member in cls)
        raise ValueError(f"{label!r} is not one of: {allowed}")

    def model_sql(self, call: str) -> str:
        return f"{self.before}{{{{ {call} }}}}{self.after}\n"
