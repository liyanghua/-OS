"""Skill Registry：可扩展能力注册系统。

借鉴 DeerFlow 的 Skill 概念：每个 Skill 是一个结构化能力模块，
包含描述、触发条件、工作流定义。按需加载，不占上下文窗口。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillDefinition(BaseModel):
    """Skill 定义。"""
    skill_id: str = ""
    skill_name: str = ""
    description: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    agent_role: str = ""
    workflow_steps: list[str] = Field(default_factory=list)
    prompt_fragment: str = ""
    enabled: bool = True
    category: str = ""


class SkillRegistry:
    """管理和发现 Skills。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._loaded_from: set[str] = set()

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.skill_id] = skill
        logger.debug("Registered skill: %s (%s)", skill.skill_name, skill.skill_id)

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(self, *, enabled_only: bool = True) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        return skills

    def find_by_keyword(self, text: str) -> list[SkillDefinition]:
        """Find skills matching keywords in text."""
        text_lower = text.lower()
        matches = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            for kw in skill.trigger_keywords:
                if kw.lower() in text_lower:
                    matches.append(skill)
                    break
        return matches

    def find_by_agent(self, agent_role: str) -> list[SkillDefinition]:
        """Find skills associated with a specific agent role."""
        return [s for s in self._skills.values() if s.agent_role == agent_role and s.enabled]

    def load_from_yaml(self, yaml_path: str | Path) -> int:
        """Load skills from a YAML file. Returns count of skills loaded."""
        path = Path(yaml_path)
        if str(path) in self._loaded_from:
            return 0
        if not path.exists():
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            skills_data = data.get("skills", [])
            if isinstance(skills_data, list):
                for item in skills_data:
                    skill = SkillDefinition(**item)
                    self.register(skill)
                self._loaded_from.add(str(path))
                return len(skills_data)
        except Exception:
            logger.debug("Failed to load skills from %s", path, exc_info=True)
        return 0

    def load_defaults(self) -> int:
        """Load built-in default skills."""
        defaults = [
            SkillDefinition(
                skill_id="trend_deep_analysis",
                skill_name="深度趋势分析",
                description="对机会卡进行多维度深度分析，包括竞品对比、市场趋势、用户画像",
                trigger_keywords=["深入分析", "竞品", "趋势", "深度"],
                agent_role="trend_analyst",
                workflow_steps=["提取机会卡关键信号", "对比同类竞品笔记", "评估市场窗口", "输出分析报告"],
                category="analysis",
            ),
            SkillDefinition(
                skill_id="brief_comparison",
                skill_name="Brief 多版本对比",
                description="对比多个 Brief 版本的差异，帮助选择最佳方向",
                trigger_keywords=["对比", "版本", "哪个好", "选哪个"],
                agent_role="brief_synthesizer",
                workflow_steps=["加载历史版本", "逐字段对比", "标注差异", "推荐最优版本"],
                category="comparison",
            ),
            SkillDefinition(
                skill_id="strategy_debate",
                skill_name="策略辩论",
                description="生成两个对立策略方向，让用户选择或融合",
                trigger_keywords=["对比方案", "两个方向", "辩论", "哪个策略"],
                agent_role="strategy_director",
                workflow_steps=["生成方向 A", "生成方向 B", "列出优劣对比", "等待人类决策"],
                category="planning",
            ),
            SkillDefinition(
                skill_id="visual_style_transfer",
                skill_name="视觉风格迁移",
                description="参考已有高分笔记的视觉风格，生成适配建议",
                trigger_keywords=["参考", "风格", "像这个", "类似"],
                agent_role="visual_director",
                workflow_steps=["分析参考图风格", "提取风格特征", "生成迁移建议", "适配到当前场景"],
                category="visual",
            ),
            SkillDefinition(
                skill_id="batch_variant",
                skill_name="批量变体生成",
                description="从一套资产包快速派生多个调性/场景变体",
                trigger_keywords=["批量", "变体", "多套", "AB测试"],
                agent_role="asset_producer",
                workflow_steps=["确定变体轴", "生成变体快照", "标注差异", "打包输出"],
                category="production",
            ),
        ]
        for skill in defaults:
            self.register(skill)
        return len(defaults)

    def reset(self) -> None:
        self._skills.clear()
        self._loaded_from.clear()


# Singleton
skill_registry = SkillRegistry()
skill_registry.load_defaults()
