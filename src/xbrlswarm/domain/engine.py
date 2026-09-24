from __future__ import annotations

from enum import StrEnum


class Engine(StrEnum):
    """可執行來源搜尋或證據擷取的 engine。"""

    MOPS = "mops"
    GOODINFO = "goodinfo"
    YAHOO = "yahoo"
    GOOGLE = "google"
    GROUNDED_AI = "grounded_ai"

    @classmethod
    def parse(cls, value: str) -> "Engine":
        try:
            return cls(value.lower())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(
                f"無效的 engine {value!r}；應為以下其中之一：{allowed}"
            ) from exc


def next_engine(engine: Engine) -> Engine | None:
    """Return the next fixed source, or None after grounded AI."""

    order = tuple(Engine)
    if not isinstance(engine, Engine):
        raise ValueError("engine must be an Engine value")
    index = order.index(engine) + 1
    return order[index] if index < len(order) else None
