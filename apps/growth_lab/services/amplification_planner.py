"""AmplificationPlanner：基于测试结果的放大决策引擎。

纯规则驱动（MVP），根据 CTR 等指标给出放大 / 再裂变 / 新钩子建议。
"""

from __future__ import annotations

import logging
from typing import Any

from apps.growth_lab.schemas.test_task import AmplificationPlan

logger = logging.getLogger(__name__)

_CTR_SCALE_THRESHOLD = 3.0
_CTR_VARIANT_THRESHOLD = 1.5


class AmplificationPlanner:
    """测试结果 → 放大计划规则引擎。"""

    async def suggest(
        self,
        task: dict,
        results: list[dict],
    ) -> AmplificationPlan:
        """分析测试任务及结果快照，生成放大计划。"""
        task_id = task.get("task_id", "")
        workspace_id = task.get("workspace_id", "")
        brand_id = task.get("brand_id", "")
        variant_type = task.get("variant_type", "main_image")

        best_ctr, best_snapshot = self._find_best_ctr(results)
        amp_type = self._decide_type(best_ctr)
        actions = self._build_actions(
            amp_type, best_ctr, best_snapshot, task, variant_type,
        )
        priority = self._decide_priority(best_ctr, amp_type)
        risk = self._assess_risk(amp_type, results)

        plan = AmplificationPlan(
            based_on_task_id=task_id,
            amplification_type=amp_type,
            recommended_actions=actions,
            priority=priority,
            expected_risk=risk,
            workspace_id=workspace_id,
            brand_id=brand_id,
            status="proposed",
        )

        logger.info(
            "放大建议: task=%s best_ctr=%.2f%% type=%s priority=%s actions=%d",
            task_id, best_ctr * 100, amp_type, priority, len(actions),
        )
        return plan

    # ── 内部方法 ──

    @staticmethod
    def _find_best_ctr(results: list[dict]) -> tuple[float, dict]:
        best_ctr = 0.0
        best_snapshot: dict[str, Any] = {}
        for r in results:
            ctr = r.get("ctr")
            if ctr is not None and ctr > best_ctr:
                best_ctr = ctr
                best_snapshot = r
        return best_ctr, best_snapshot

    @staticmethod
    def _decide_type(best_ctr: float) -> str:
        best_pct = best_ctr * 100
        if best_pct >= _CTR_SCALE_THRESHOLD:
            return "original_link_scale"
        if best_pct >= _CTR_VARIANT_THRESHOLD:
            return "same_product_variant"
        return "new_hook_variant"

    @staticmethod
    def _build_actions(
        amp_type: str,
        best_ctr: float,
        best_snapshot: dict,
        task: dict,
        variant_type: str,
    ) -> list[str]:
        actions: list[str] = []
        best_pct = best_ctr * 100
        platform = task.get("platform", "")

        if amp_type == "original_link_scale":
            actions.append(f"当前最佳 CTR {best_pct:.1f}%，建议直接放大原链接投放")
            actions.append("增加投放预算至当前 2-3 倍")
            if platform:
                actions.append(f"在 {platform} 扩大人群包覆盖")
            actions.append("密切监控 7 天 ROI 变化")

        elif amp_type == "same_product_variant":
            actions.append(f"当前最佳 CTR {best_pct:.1f}%，建议同品裂变新版本")
            if variant_type == "main_image":
                actions.append("保留当前最优主图，新增 2-3 个构图/场景变体")
                actions.append("重点测试模特/背景/字卡维度")
            else:
                actions.append("保留当前最优钩子类型，换用新文案角度")
                actions.append("重点测试不同 opening_line 变体")
            actions.append("小流量 AB 测试 3-5 天")

        else:
            actions.append(f"当前最佳 CTR {best_pct:.1f}%，建议更换钩子方向")
            actions.append("分析当前版本失败原因：受众匹配度 / 卖点切入角度 / 视觉吸引力")
            actions.append("重新从卖点编译器获取新角度")
            if variant_type == "first3s":
                actions.append("尝试不同钩子类型（question → contrast / shock）")
            else:
                actions.append("尝试不同视觉风格或构图方案")

        conversion = best_snapshot.get("conversion_rate")
        if conversion is not None and conversion < 0.01:
            actions.append("注意：转化率偏低，需排查落地页 / 价格 / 详情页问题")

        refund = best_snapshot.get("refund_rate")
        if refund is not None and refund > 0.1:
            actions.append("警告：退款率超 10%，需检查产品质量或描述匹配度")

        return actions

    @staticmethod
    def _decide_priority(best_ctr: float, amp_type: str) -> str:
        if amp_type == "original_link_scale":
            return "high"
        if amp_type == "same_product_variant":
            return "medium"
        return "low"

    @staticmethod
    def _assess_risk(amp_type: str, results: list[dict]) -> str:
        if amp_type == "original_link_scale":
            refund_rates = [r.get("refund_rate", 0) or 0 for r in results]
            max_refund = max(refund_rates) if refund_rates else 0
            if max_refund > 0.08:
                return "中风险：退款率偏高，放大后可能放大退款问题"
            return "低风险：CTR 表现良好，放大投放风险可控"

        if amp_type == "same_product_variant":
            return "中风险：需要额外裂变成本，但基于已有正向信号"

        return "高风险：当前版本表现不佳，需重新探索方向"
