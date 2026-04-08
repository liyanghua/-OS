"""对象字段级锁定：防止下游重生成覆盖已确认的内容。"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ObjectLock(BaseModel):
    """字段级锁定状态。"""

    locked_fields: dict[str, bool] = Field(default_factory=dict)
    locked_by: str | None = None
    locked_at: datetime | None = None

    def is_locked(self, field: str) -> bool:
        return self.locked_fields.get(field, False)

    def lock(self, field: str, by: str = "") -> None:
        self.locked_fields[field] = True
        self.locked_by = by
        self.locked_at = datetime.now(UTC)

    def unlock(self, field: str) -> None:
        self.locked_fields.pop(field, None)

    def locked_field_names(self) -> list[str]:
        return [k for k, v in self.locked_fields.items() if v]
