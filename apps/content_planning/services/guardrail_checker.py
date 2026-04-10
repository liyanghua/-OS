"""品牌 Guardrail 检查器：在四阶段 build / apply 前检测品牌合规。"""
from __future__ import annotations
from typing import Any


def check_guardrails(content: dict[str, Any], guardrails: dict[str, Any]) -> dict[str, Any]:
    """Check content dict against brand guardrails.

    Returns dict with:
    - warnings: list[str] — human-readable warning messages
    - blocked: bool — whether any hard violation found
    - brand_fit_score: float — 0.0 to 1.0
    """
    warnings: list[str] = []
    violations = 0
    total_checks = 0

    forbidden = guardrails.get("forbidden_expressions", [])
    must_mention = guardrails.get("must_mention_points", [])
    risk_words = guardrails.get("risk_words", [])

    text_fields = []
    for _key, val in content.items():
        if isinstance(val, str):
            text_fields.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    text_fields.append(item)
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str):
                            text_fields.append(v)

    full_text = " ".join(text_fields).lower()

    # Check forbidden expressions
    for expr in forbidden:
        total_checks += 1
        if expr.lower() in full_text:
            warnings.append(f"包含禁用表达：「{expr}」")
            violations += 1

    # Check must-mention points
    for point in must_mention:
        total_checks += 1
        if point.lower() not in full_text:
            warnings.append(f"缺少必提点：「{point}」")
            violations += 1

    # Check risk words
    for word in risk_words:
        total_checks += 1
        if word.lower() in full_text:
            warnings.append(f"包含风险词：「{word}」")
            violations += 1

    if total_checks == 0:
        brand_fit_score = 1.0
    else:
        brand_fit_score = max(0.0, 1.0 - (violations / max(total_checks, 1)))

    blocked = any(
        w.startswith("包含禁用表达") for w in warnings
    )

    return {
        "warnings": warnings,
        "blocked": blocked,
        "brand_fit_score": round(brand_fit_score, 3),
    }
