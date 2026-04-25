"""rulepack_builder — 把审核通过的 RuleSpec 聚合为 active RulePack。

约定：
- 同 category 多版本共存（v1, v2, ...），但只有一个 status='active'。
- 构建时可指定 `default_strategy_archetypes`；如未传且 category 是
  children_desk_mat，则使用内置 6 archetype。
- 每条被纳入的 RuleSpec 会写入 rule.rule_pack_id，建立反向引用。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apps.content_planning.schemas.rule_pack import (
    CHILDREN_DESK_MAT_ARCHETYPES,
    ArchetypeConfig,
    RulePack,
    RulePackMetrics,
)
from apps.content_planning.schemas.rule_spec import RuleSpec
from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)


_BUILTIN_ARCHETYPES: dict[str, list[ArchetypeConfig]] = {
    "children_desk_mat": CHILDREN_DESK_MAT_ARCHETYPES,
}


def _now() -> datetime:
    return datetime.now(UTC)


class RulePackBuilder:
    def __init__(self, store: RuleStore | None = None) -> None:
        self.store = store or RuleStore()

    def build(
        self,
        *,
        category: str,
        version: str | None = None,
        name: str | None = None,
        description: str = "",
        archetypes: list[ArchetypeConfig] | None = None,
        include_status: list[str] | None = None,
        activate: bool = True,
    ) -> RulePack:
        include_status = include_status or ["approved"]
        rules_data = self.store.list_rule_specs(category=category)
        eligible = [r for r in rules_data if r.get("review", {}).get("status") in include_status]

        archetype_list = archetypes if archetypes is not None else _BUILTIN_ARCHETYPES.get(category, [])

        version = version or self._next_version(category)
        name = name or f"rulepack_{category}_{version}"

        confidences = [r.get("evidence", {}).get("confidence", 0.0) for r in eligible]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        pack = RulePack(
            category=category,
            name=name,
            version=version,
            description=description,
            dimensions=sorted({r.get("dimension", "") for r in eligible}),
            rule_ids=[r["id"] for r in eligible],
            default_strategy_archetypes=archetype_list,
            status="draft",
            metrics=RulePackMetrics(
                rule_count=len(rules_data),
                approved_rule_count=len(eligible),
                avg_confidence=round(avg_conf, 4),
            ),
        )

        # 写包
        self.store.save_rule_pack(pack.model_dump())

        # 绑定每条规则的 rule_pack_id
        for raw in eligible:
            rule = RuleSpec(**raw)
            rule.rule_pack_id = pack.id
            rule.lifecycle.updated_at = _now()
            self.store.save_rule_spec(rule.model_dump())

        if activate:
            self.activate(pack.id, category=category)
            pack.status = "active"
            pack = self._reload(pack.id) or pack

        logger.info(
            "[rulepack_build] category=%s version=%s rules=%d/%d active=%s",
            category, version, len(eligible), len(rules_data), activate,
        )
        return pack

    def activate(self, rule_pack_id: str, *, category: str) -> RulePack | None:
        existing = self.store.list_rule_packs(category=category)
        for raw in existing:
            if raw.get("status") == "active" and raw["id"] != rule_pack_id:
                raw["status"] = "archived"
                raw["updated_at"] = _now().isoformat()
                self.store.save_rule_pack(raw)

        target = self.store.get_rule_pack(rule_pack_id)
        if not target:
            return None
        target["status"] = "active"
        target["updated_at"] = _now().isoformat()
        self.store.save_rule_pack(target)
        return RulePack(**target)

    def _next_version(self, category: str) -> str:
        existing = self.store.list_rule_packs(category=category)
        next_n = len(existing) + 1
        return f"v{next_n}"

    def _reload(self, rule_pack_id: str) -> RulePack | None:
        raw = self.store.get_rule_pack(rule_pack_id)
        return RulePack(**raw) if raw else None
