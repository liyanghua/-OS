"""选择器版本注册表 + fallback 链。

每种页面类型（search / note_detail / comment）可注册多个版本的抽取器。
get_extractor() 按版本倒序尝试 validate，返回第一个匹配的版本。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol

logger = logging.getLogger("extractors")


class Extractor(Protocol):
    """抽取器协议——所有版本化 extractor 必须实现。"""

    name: str
    version: str
    page_type: str
    last_verified_at: str

    def validate(self, data: dict[str, Any]) -> bool:
        """验证原始数据结构是否匹配此版本。"""
        ...

    def extract(self, data: dict[str, Any]) -> dict[str, Any]:
        """从原始数据中抽取标准化字段。"""
        ...


@dataclass
class ExtractorEntry:
    extractor: Extractor
    priority: int = 0  # higher = tried first


class ExtractorRegistry:
    """全局 extractor 注册表，按 page_type 分组管理。"""

    def __init__(self) -> None:
        self._registry: dict[str, list[ExtractorEntry]] = {}

    def register(self, extractor: Extractor, priority: int = 0) -> None:
        page_type = extractor.page_type
        if page_type not in self._registry:
            self._registry[page_type] = []
        self._registry[page_type].append(
            ExtractorEntry(extractor=extractor, priority=priority)
        )
        self._registry[page_type].sort(key=lambda e: e.priority, reverse=True)

    def get(self, page_type: str, data: dict[str, Any]) -> Extractor | None:
        entries = self._registry.get(page_type, [])
        for entry in entries:
            try:
                if entry.extractor.validate(data):
                    return entry.extractor
            except Exception as ex:
                logger.debug(
                    f"[ExtractorRegistry] validate failed for "
                    f"{entry.extractor.name}@{entry.extractor.version}: {ex}"
                )
        return None

    def list_versions(self, page_type: str) -> list[dict[str, str]]:
        entries = self._registry.get(page_type, [])
        return [
            {
                "name": e.extractor.name,
                "version": e.extractor.version,
                "last_verified_at": e.extractor.last_verified_at,
            }
            for e in entries
        ]

    def all_versions(self) -> dict[str, str]:
        """返回 {page_type: version} 当前活跃版本映射。"""
        result = {}
        for page_type, entries in self._registry.items():
            if entries:
                result[page_type] = entries[0].extractor.version
        return result


_default_registry = ExtractorRegistry()


def get_registry() -> ExtractorRegistry:
    return _default_registry


def get_extractor(page_type: str, data: dict[str, Any]) -> Extractor | None:
    return _default_registry.get(page_type, data)
