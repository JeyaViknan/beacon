"""DynamoDB value conversion and UpdateExpression building."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any


def to_ddb(value: Any) -> Any:
    """Python/JSON values -> what boto3's resource layer accepts (floats become Decimal)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {k: to_ddb(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_ddb(v) for v in value]
    return value


def from_ddb(value: Any) -> Any:
    """boto3 values -> plain JSON-friendly Python (Decimal becomes int or float)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, Mapping):
        return {k: from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_ddb(v) for v in value]
    return value


def without_none(item: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if v is not None}


class Update:
    """Builds ``SET``/``REMOVE``/``ADD`` expressions with safe placeholder names."""

    def __init__(self) -> None:
        self._set: list[str] = []
        self._remove: list[str] = []
        self._add: list[str] = []
        self.names: dict[str, str] = {}
        self.values: dict[str, Any] = {}

    def _name(self, attr: str) -> str:
        key = f"#n{len(self.names)}"
        self.names[key] = attr
        return key

    def _value(self, value: Any) -> str:
        key = f":v{len(self.values)}"
        self.values[key] = to_ddb(value)
        return key

    def set(self, attr: str, value: Any) -> "Update":
        """``SET attr = value``; ``None`` turns into ``REMOVE attr``."""
        if value is None:
            self._remove.append(self._name(attr))
        else:
            self._set.append(f"{self._name(attr)} = {self._value(value)}")
        return self

    def set_many(self, fields: Mapping[str, Any]) -> "Update":
        for attr, value in fields.items():
            self.set(attr, value)
        return self

    def add(self, attr: str, amount: int) -> "Update":
        self._add.append(f"{self._name(attr)} {self._value(amount)}")
        return self

    def append(self, attr: str, items: list[Any]) -> "Update":
        name = self._name(attr)
        empty = self._value([])
        self._set.append(
            f"{name} = list_append(if_not_exists({name}, {empty}), {self._value(items)})"
        )
        return self

    def value(self, value: Any) -> str:
        """Register a value for use in a condition expression."""
        return self._value(value)

    def name(self, attr: str) -> str:
        return self._name(attr)

    @property
    def expression(self) -> str:
        parts = []
        if self._set:
            parts.append("SET " + ", ".join(self._set))
        if self._remove:
            parts.append("REMOVE " + ", ".join(self._remove))
        if self._add:
            parts.append("ADD " + ", ".join(self._add))
        return " ".join(parts)

    def kwargs(self, condition: str | None = None) -> dict[str, Any]:
        """Keyword arguments for ``Table.update_item``."""
        out: dict[str, Any] = {
            "UpdateExpression": self.expression,
            "ExpressionAttributeNames": self.names,
        }
        if self.values:
            out["ExpressionAttributeValues"] = self.values
        if condition:
            out["ConditionExpression"] = condition
        return out
