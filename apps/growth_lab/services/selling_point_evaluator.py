"""SellingPointEvaluator：规则打分为主，评估编译质量并给出改进建议。"""

from __future__ import annotations

from typing import Any


class EvaluationDimension:
    __slots__ = ("label", "score", "hint")

    def __init__(self, label: str, score: float, hint: str) -> None:
        self.label = label
        self.score = max(0.0, min(1.0, score))
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "score": round(self.score, 2), "hint": self.hint}


class SellingPointEvaluator:
    """规则驱动的卖点质量评估器。"""

    def evaluate(self, spec: dict) -> dict[str, Any]:
        dims = self._score_dimensions(spec)
        avg = sum(d.score for d in dims) / len(dims) if dims else 0.0
        overall_label = "优秀" if avg >= 0.7 else "良好" if avg >= 0.5 else "需完善"
        return {
            "overall_score": round(avg, 2),
            "overall_label": overall_label,
            "dimensions": [d.to_dict() for d in dims],
            "next_steps": self._suggest_next_steps(spec, avg),
        }

    def _score_dimensions(self, spec: dict) -> list[EvaluationDimension]:
        dims: list[EvaluationDimension] = []

        claim = spec.get("core_claim", "") or ""
        if 6 <= len(claim) <= 40:
            dims.append(EvaluationDimension("卖点清晰度", 0.8, "长度适中"))
        elif claim:
            hint = "核心主张过短，建议更具体" if len(claim) < 6 else "核心主张过长，建议精炼"
            dims.append(EvaluationDimension("卖点清晰度", 0.5, hint))
        else:
            dims.append(EvaluationDimension("卖点清晰度", 0.1, "缺少核心主张"))

        people = spec.get("target_people", []) or []
        if len(people) >= 2:
            dims.append(EvaluationDimension("人群精准度", 0.8, "人群定位清晰"))
        elif len(people) == 1:
            dims.append(EvaluationDimension("人群精准度", 0.5, "建议补充更细分人群"))
        else:
            dims.append(EvaluationDimension("人群精准度", 0.1, "缺少目标人群"))

        scenarios = spec.get("target_scenarios", []) or []
        if len(scenarios) >= 2:
            dims.append(EvaluationDimension("场景可感知度", 0.8, "场景描述具体"))
        elif len(scenarios) == 1:
            dims.append(EvaluationDimension("场景可感知度", 0.5, "建议补充具体使用场景"))
        else:
            dims.append(EvaluationDimension("场景可感知度", 0.1, "缺少目标场景"))

        supporting = spec.get("supporting_claims", []) or []
        count = len(supporting)
        if count >= 3:
            dims.append(EvaluationDimension("支撑充分度", 0.9, f"{count} 条支撑论据"))
        elif count >= 2:
            dims.append(EvaluationDimension("支撑充分度", 0.7, f"{count} 条支撑论据"))
        elif count == 1:
            dims.append(EvaluationDimension("支撑充分度", 0.4, "支撑不足，建议补充"))
        else:
            dims.append(EvaluationDimension("支撑充分度", 0.1, "缺少支撑论据"))

        has_shelf = bool(spec.get("shelf_expression") and isinstance(spec["shelf_expression"], dict) and spec["shelf_expression"].get("headline"))
        has_first3s = bool(spec.get("first3s_expression") and isinstance(spec["first3s_expression"], dict) and spec["first3s_expression"].get("headline"))
        if has_shelf and has_first3s:
            dims.append(EvaluationDimension("可执行度", 0.9, "货架和前3秒表达均已就绪"))
        elif has_shelf or has_first3s:
            dims.append(EvaluationDimension("可执行度", 0.6, "平台表达不完整"))
        else:
            dims.append(EvaluationDimension("可执行度", 0.2, "缺少平台表达"))

        diff = spec.get("differentiation_notes", "") or ""
        if len(diff) > 10:
            dims.append(EvaluationDimension("差异化与风险", 0.7, "已有差异化说明"))
        elif diff:
            dims.append(EvaluationDimension("差异化与风险", 0.4, "差异化说明较简略"))
        else:
            dims.append(EvaluationDimension("差异化与风险", 0.2, "建议补充竞品差异化分析"))

        return dims

    @staticmethod
    def _suggest_next_steps(spec: dict, avg_score: float) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        spec_id = spec.get("spec_id", "")

        has_shelf = bool(spec.get("shelf_expression") and isinstance(spec["shelf_expression"], dict) and spec["shelf_expression"].get("headline"))
        has_first3s = bool(spec.get("first3s_expression") and isinstance(spec["first3s_expression"], dict) and spec["first3s_expression"].get("headline"))

        if has_shelf and spec_id:
            steps.append({"label": "进入主图工作台", "url": f"/growth-lab/lab?spec_id={spec_id}", "type": "primary"})
        if has_first3s and spec_id:
            steps.append({"label": "进入前3秒工作台", "url": f"/growth-lab/first3s?spec_id={spec_id}", "type": "secondary"})
        if avg_score < 0.6:
            steps.append({"label": "继续优化卖点", "url": "", "type": "optimize"})

        return steps
