"""视觉通道映射状态。"""

from dataclasses import dataclass


@dataclass
class Mapping:
    """记录每个视觉通道绑定的字段名。"""

    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    y2: str | None = None

    def set(self, slot: str, field: str) -> None:
        if not hasattr(self, slot):
            raise KeyError(f"未知槽位: {slot}")
        setattr(self, slot, field)