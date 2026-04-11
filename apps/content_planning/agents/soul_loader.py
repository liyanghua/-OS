"""Load Council role SOUL.md (Hermes-style identity slot)."""
from __future__ import annotations

import logging
from pathlib import Path

from apps.content_planning.agents.soul_context_hermes import scan_context_content, truncate_content

logger = logging.getLogger(__name__)

_SOULS_DIR = Path(__file__).resolve().parent / "souls"

# One-line positioning for UI when SOUL is missing or first line parse fails
SOUL_ROLE_TAGLINES: dict[str, str] = {
    "brand_guardian": "品牌一致性与调性合规",
    "growth_strategist": "增长、转化与平台机制",
    "creative_director": "创意叙事与差异化表达",
    "risk_assessor": "合规、舆情与不确定性",
    "lead_synthesizer": "综合共识与结构化提案",
    # legacy ids (fallback)
    "trend_analyst": "趋势与市场时机",
    "brief_synthesizer": "Brief 与策划结构",
    "template_planner": "模板与结构匹配",
    "strategy_director": "内容策略与差异化",
    "visual_director": "视觉与图位节奏",
    "asset_producer": "资产包与可交付产出",
}


class SoulLoader:
    """Load SOUL.md per role_id from souls/{role_id}/SOUL.md with scan + truncate + cache."""

    def __init__(self, souls_dir: Path | None = None) -> None:
        self._dir = souls_dir or _SOULS_DIR
        self._cache: dict[str, str] = {}

    def list_roles(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(p.name for p in self._dir.iterdir() if p.is_dir() and (p / "SOUL.md").is_file())

    def tagline(self, role_id: str) -> str:
        return SOUL_ROLE_TAGLINES.get(role_id, role_id)

    def load(self, role_id: str) -> str:
        if role_id in self._cache:
            return self._cache[role_id]
        path = self._dir / role_id / "SOUL.md"
        if not path.is_file():
            text = self._fallback_soul(role_id)
            self._cache[role_id] = text
            return text
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning("SOUL read failed %s: %s", path, e)
            text = self._fallback_soul(role_id)
            self._cache[role_id] = text
            return text
        scanned = scan_context_content(raw, f"{role_id}/SOUL.md")
        text = truncate_content(scanned, f"{role_id}/SOUL.md")
        if not text.strip():
            text = self._fallback_soul(role_id)
        self._cache[role_id] = text
        return text

    def _fallback_soul(self, role_id: str) -> str:
        line = self.tagline(role_id)
        return f"# {role_id}\n\n你是委员会成员，专注领域：{line}。\n请基于用户问题与上下文给出专业、可执行的观点。"

    def invalidate_cache(self) -> None:
        self._cache.clear()
