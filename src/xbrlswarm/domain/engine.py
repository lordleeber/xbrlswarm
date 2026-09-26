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


# Goodinfo 對自動化 client 回 Cloudflare managed challenge，Step-41–43 閘門暫停。
PAUSED_ENGINES: frozenset[Engine] = frozenset({Engine.GOODINFO})


def next_active_engine(
    engine: Engine, paused: frozenset[Engine] = PAUSED_ENGINES
) -> Engine | None:
    """Return the next fixed source that is not paused, or None after grounded AI."""

    candidate = next_engine(engine)
    while candidate in paused:
        candidate = next_engine(candidate)
    return candidate
