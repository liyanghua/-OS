"""TemplateLibrary — 模板资产运行期目录。

两类来源：
1. `apps/growth_lab/templates_lib/*.yaml` — 精简模板（legacy / 兜底）。
2. `assets/**` — 业务专家富资产（YAML Schema v2、详情/视频/买家秀/竞品 MD）。

加载顺序：templates_lib 先加载（作为兜底），然后 assets/ 覆盖同 category 的默认
并追加到库里；两边都存在时，同 category 的"默认模板"优先取 assets 源，
让 `assets/` 真正成为 source of truth。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from apps.growth_lab.schemas.visual_workspace import ScriptTemplate, TemplateSlot
from apps.growth_lab.services.expert_asset_loader import load_expert_assets

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates_lib"


class TemplateLibrary:
    """业务专家策划模板的运行期目录。"""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or _TEMPLATES_DIR
        self._templates: dict[str, ScriptTemplate] = {}
        # 每个 category 的首选（用于 default_for_category）
        self._category_preferred: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        self._load_simple_yaml()
        self._load_expert_assets()

    def _load_simple_yaml(self) -> None:
        if not self._dir.exists():
            logger.warning("模板目录不存在: %s", self._dir)
            return
        for yaml_path in sorted(self._dir.glob("*.yaml")):
            try:
                with yaml_path.open("r", encoding="utf-8") as fh:
                    raw: dict[str, Any] = yaml.safe_load(fh) or {}
                slots = [TemplateSlot(**s) for s in raw.get("slots", [])]
                tpl = ScriptTemplate(
                    template_id=raw.get("template_id", yaml_path.stem),
                    category=raw.get("category", "main_image"),
                    name=raw.get("name", ""),
                    description=raw.get("description", ""),
                    slots=slots,
                    default_brand_rules=raw.get("default_brand_rules", []) or [],
                    yaml_source_path=str(yaml_path.relative_to(self._dir.parent.parent)),
                    version=raw.get("version", "v1"),
                    source_kind="yaml_simple",
                )
                self._templates[tpl.template_id] = tpl
                # 精简模板是 category 的兜底默认
                self._category_preferred.setdefault(tpl.category, tpl.template_id)
                logger.info(
                    "加载精简模板: %s (%s, %d slots)",
                    tpl.template_id, tpl.category, len(tpl.slots),
                )
            except Exception as exc:
                logger.exception("精简模板加载失败: %s — %s", yaml_path, exc)

    def _load_expert_assets(self) -> None:
        for tpl in load_expert_assets():
            self._templates[tpl.template_id] = tpl
            # assets/ 的富模板覆盖对应 category 的默认
            self._category_preferred[tpl.category] = tpl.template_id
            logger.info(
                "加载专家资产: %s (%s, %d slots, kind=%s)",
                tpl.template_id, tpl.category, len(tpl.slots), tpl.source_kind,
            )

    def get(self, template_id: str) -> ScriptTemplate | None:
        return self._templates.get(template_id)

    def list_by_category(self, category: str) -> list[ScriptTemplate]:
        return [t for t in self._templates.values() if t.category == category]

    def list_all(self) -> list[ScriptTemplate]:
        return list(self._templates.values())

    def register(self, tpl: ScriptTemplate) -> None:
        """运行时注册一个临时模板（如 adapted_template），允许按 id 查找。

        不改 _category_preferred，所以不会影响"默认模板"语义。
        """
        if not tpl.template_id:
            return
        self._templates[tpl.template_id] = tpl

    def default_for_category(self, category: str) -> ScriptTemplate | None:
        """返回某 category 的首选模板（若 assets/ 中有专家版则优先）。"""
        preferred_id = self._category_preferred.get(category)
        if preferred_id and preferred_id in self._templates:
            return self._templates[preferred_id]
        items = self.list_by_category(category)
        return items[0] if items else None


_instance: TemplateLibrary | None = None


def get_template_library() -> TemplateLibrary:
    global _instance
    if _instance is None:
        _instance = TemplateLibrary()
    return _instance
