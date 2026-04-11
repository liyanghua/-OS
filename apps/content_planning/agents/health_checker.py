"""HealthChecker: Stage-aware health checks for Brief, Strategy, Plan, and Asset.

Outputs HealthIssue[] that the frontend renders as alert bars + next_best_action chips.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthIssue(BaseModel):
    """Single health check finding."""
    severity: str = "warning"  # error | warning | info
    dimension: str = ""  # field name or check category
    message: str = ""
    suggestion: str = ""
    target_field: str = ""


class HealthCheckResult(BaseModel):
    """Aggregated health check output."""
    stage: str = ""
    issues: list[HealthIssue] = Field(default_factory=list)
    score: float = 1.0
    next_best_action: str = ""
    next_best_action_type: str = ""  # regenerate / refine / discuss / lock

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def is_healthy(self) -> bool:
        return not self.has_errors and self.score >= 0.6


class HealthChecker:
    """Run health checks on stage objects."""

    def check_brief_health(self, brief: Any) -> HealthCheckResult:
        """Check Brief completeness and consistency."""
        result = HealthCheckResult(stage="brief")
        if brief is None:
            result.issues.append(HealthIssue(
                severity="error", dimension="brief", message="Brief 尚未生成",
                suggestion="请先编译 Brief", target_field="brief",
            ))
            result.score = 0.0
            result.next_best_action = "生成 Brief"
            result.next_best_action_type = "generate"
            return result

        required_fields = [
            ("target_user", "目标用户"),
            ("content_goal", "内容目标"),
            ("primary_value", "核心价值"),
        ]
        optional_fields = [
            ("target_scene", "使用场景"),
            ("visual_style_direction", "视觉风格方向"),
            ("avoid_directions", "避免方向"),
            ("why_now", "为什么是现在"),
        ]

        missing_required = 0
        for field_name, label in required_fields:
            value = getattr(brief, field_name, None) if not isinstance(brief, dict) else brief.get(field_name)
            if not value or (isinstance(value, str) and not value.strip()):
                result.issues.append(HealthIssue(
                    severity="error", dimension=field_name,
                    message=f"必填字段「{label}」为空",
                    suggestion=f"请填写或让 AI 生成 {label}",
                    target_field=field_name,
                ))
                missing_required += 1

        missing_optional = 0
        for field_name, label in optional_fields:
            value = getattr(brief, field_name, None) if not isinstance(brief, dict) else brief.get(field_name)
            if not value or (isinstance(value, str) and not value.strip()):
                result.issues.append(HealthIssue(
                    severity="info", dimension=field_name,
                    message=f"可选字段「{label}」为空",
                    suggestion=f"补充 {label} 可提升策略质量",
                    target_field=field_name,
                ))
                missing_optional += 1

        total = len(required_fields) + len(optional_fields)
        filled = total - missing_required - missing_optional
        result.score = filled / total if total > 0 else 0.0

        if missing_required > 0:
            result.next_best_action = f"填写 {missing_required} 个必填字段"
            result.next_best_action_type = "refine"
        elif missing_optional > 0:
            result.next_best_action = f"可补充 {missing_optional} 个可选字段"
            result.next_best_action_type = "refine"
        else:
            result.next_best_action = "Brief 完整，可进入策略生成"
            result.next_best_action_type = "lock"

        return result

    def check_strategy_health(self, strategy: Any, brief: Any = None) -> HealthCheckResult:
        """Check Strategy coverage and consistency with Brief."""
        result = HealthCheckResult(stage="strategy")
        if strategy is None:
            result.issues.append(HealthIssue(
                severity="error", dimension="strategy", message="策略尚未生成",
                suggestion="请先生成策略", target_field="strategy",
            ))
            result.score = 0.0
            result.next_best_action = "生成策略"
            result.next_best_action_type = "generate"
            return result

        checks = [
            ("positioning_statement", "定位声明"),
            ("tone_of_voice", "调性"),
            ("new_hook", "钩子"),
        ]
        missing = 0
        for field_name, label in checks:
            value = getattr(strategy, field_name, None) if not isinstance(strategy, dict) else strategy.get(field_name)
            if not value:
                result.issues.append(HealthIssue(
                    severity="warning", dimension=field_name,
                    message=f"策略字段「{label}」为空",
                    suggestion=f"AI 可自动生成 {label}",
                    target_field=field_name,
                ))
                missing += 1

        if brief is not None:
            brief_goal = getattr(brief, "content_goal", None) or (brief.get("content_goal") if isinstance(brief, dict) else "")
            strat_positioning = getattr(strategy, "positioning_statement", None) or (strategy.get("positioning_statement", "") if isinstance(strategy, dict) else "")
            if brief_goal and strat_positioning and brief_goal not in strat_positioning:
                result.issues.append(HealthIssue(
                    severity="info", dimension="consistency",
                    message="策略定位与 Brief 目标可能不一致",
                    suggestion="检查策略是否覆盖核心内容目标",
                ))

        result.score = max(0.0, 1.0 - missing * 0.25)
        if result.has_errors:
            result.next_best_action = "生成策略"
            result.next_best_action_type = "generate"
        elif missing:
            result.next_best_action = f"补充 {missing} 个策略字段"
            result.next_best_action_type = "refine"
        else:
            result.next_best_action = "策略就绪，可进入内容计划"
            result.next_best_action_type = "lock"

        return result

    def check_plan_health(self, plan: Any, strategy: Any = None) -> HealthCheckResult:
        """Check plan completeness and consistency with strategy."""
        result = HealthCheckResult(stage="plan")
        if plan is None:
            result.issues.append(HealthIssue(
                severity="error", dimension="plan", message="内容计划尚未生成",
                suggestion="请先编译内容计划",
            ))
            result.score = 0.0
            result.next_best_action = "编译内容计划"
            result.next_best_action_type = "generate"
            return result

        theme = getattr(plan, "theme", None) or (plan.get("theme") if isinstance(plan, dict) else "")
        if not theme:
            result.issues.append(HealthIssue(
                severity="warning", dimension="theme", message="计划主题为空",
                suggestion="AI 可基于策略自动推断主题",
            ))

        result.score = 0.8 if not result.issues else 0.5
        result.next_best_action = "计划就绪" if result.is_healthy else "补充计划细节"
        result.next_best_action_type = "lock" if result.is_healthy else "refine"
        return result

    def check_asset_health(self, asset_bundle: Any, plan: Any = None) -> HealthCheckResult:
        """Check asset bundle completeness."""
        result = HealthCheckResult(stage="asset")
        if asset_bundle is None:
            result.issues.append(HealthIssue(
                severity="error", dimension="asset_bundle", message="资产包尚未组装",
                suggestion="请先组装资产包",
            ))
            result.score = 0.0
            result.next_best_action = "组装资产包"
            result.next_best_action_type = "generate"
            return result

        result.score = 0.8
        result.next_best_action = "资产包就绪，可评审"
        result.next_best_action_type = "evaluate"
        return result

    def check(self, stage: str, **objects: Any) -> HealthCheckResult:
        """Dispatch to stage-specific checker."""
        if stage in ("brief", "策略规划"):
            return self.check_brief_health(objects.get("brief"))
        elif stage in ("strategy", "策略"):
            return self.check_strategy_health(objects.get("strategy"), objects.get("brief"))
        elif stage in ("plan", "content", "内容计划"):
            return self.check_plan_health(objects.get("plan"), objects.get("strategy"))
        elif stage in ("asset", "资产"):
            return self.check_asset_health(objects.get("asset_bundle"), objects.get("plan"))
        return HealthCheckResult(stage=stage, score=1.0)
