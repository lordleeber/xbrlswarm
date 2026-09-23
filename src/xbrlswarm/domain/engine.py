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
