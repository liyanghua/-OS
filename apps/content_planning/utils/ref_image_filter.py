"""参考图 URL 健壮性过滤。

视觉工作台/生图链路里，来源笔记的 ``cover_image`` 与 ``image_urls`` 可能是
fixture / mock 占位 URL（如 ``https://example.com/img1.jpg``）或空串/损坏 URL。
直接送给 OpenRouter 的多模态接口会触发 400 错误（``Unable to extract dimensions``）。

本模块提供单一入口 :func:`is_usable_ref_url`，被以下 3 处接入：

- ``apps/intel_hub/api/app.py::_persist_source_images``
- ``apps/content_planning/api/routes.py::_build_rich_prompts``
- ``apps/content_planning/services/image_generator.py::_generate_openrouter_once``
"""
from __future__ import annotations

from typing import Iterable


INVALID_HOST_SUBSTR: tuple[str, ...] = (
    "example.com",
    "example.org",
    "example.net",
    "mock-cdn.example.com",
    "placeholder.invalid",
    "localhost.invalid",
)
"""命中即视为不可用的域名/主机片段（小写匹配）。"""


def is_usable_ref_url(url: str | None) -> bool:
    """判断一个参考图 URL 是否值得送进多模态生图。

    规则：
    - 必须是非空字符串
    - 必须以 ``http://`` / ``https://`` / ``/`` 开头（后者表示本地 static 路径）
    - 不能命中 :data:`INVALID_HOST_SUBSTR` 里的占位/Mock 主机
    """
    if not url or not isinstance(url, str):
        return False
    s = url.strip()
    if not s:
        return False
    lower = s.lower()
    if not (lower.startswith("http://") or lower.startswith("https://") or lower.startswith("/")):
        return False
    if any(bad in lower for bad in INVALID_HOST_SUBSTR):
        return False
    return True


def filter_usable_ref_urls(urls: Iterable[str | None]) -> list[str]:
    """对一组 URL 做过滤并保序去重。"""
    seen: set[str] = set()
    out: list[str] = []
    for u in urls or []:
        if not is_usable_ref_url(u):
            continue
        s = (u or "").strip()
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
