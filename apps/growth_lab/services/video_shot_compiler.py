"""VideoShotCompiler — 视频分镜 prompt 增强器。

针对视频分镜模板（12 镜头默认），给每个镜头补足"景别 / 运镜 / 节奏"上下文，
把 keyframe 生成为静态图（供画布预览 + 后续作为视频生成的参考帧）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VideoShotCompiler:
    """分镜节点 prompt 增强器。"""

    def enhance_node_prompt(
        self,
        node: dict,
        *,
        intent: dict | None = None,
        shot_extra: dict | None = None,
    ) -> str:
        intent = intent or {}
        shot_extra = shot_extra or node.get("extra", {}) or {}
        parts: list[str] = [
            f"[视频关键帧 · 镜头 {node.get('slot_index')} · 比例 9:16]",
        ]
        if intent.get("product_name"):
            parts.append(f"商品：{intent['product_name']}")
        if shot_extra.get("category"):
            parts.append(f"镜头类别：{shot_extra['category']}")
        if shot_extra.get("shot_size"):
            parts.append(f"景别：{shot_extra['shot_size']}")
        if shot_extra.get("camera_move"):
            parts.append(f"运镜：{shot_extra['camera_move']}")
        if shot_extra.get("real_person"):
            parts.append("真人出镜：是")
        if node.get("role"):
            parts.append(f"镜头目标：{node['role']}")
        if node.get("visual_spec"):
            parts.append(f"画面内容：{node['visual_spec']}")
        if node.get("copy_spec"):
            parts.append(f"画面文案/口播：{node['copy_spec']}")
        parts.append("风格：生活化、光线自然、面部表情真实、避免过度美颜")
        return "\n".join(parts)


_instance: VideoShotCompiler | None = None


def get_video_shot_compiler() -> VideoShotCompiler:
    global _instance
    if _instance is None:
        _instance = VideoShotCompiler()
    return _instance
