"""run_pipeline 各阶段统计与日志辅助（与业务逻辑解耦，便于测试脚本复用）。"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from apps.intel_hub.schemas.signal import Signal

logger = logging.getLogger(__name__)


def _is_mediacrawler_raw(rec: dict[str, Any]) -> bool:
    return str(rec.get("raw_source_type") or "").startswith("mediacrawler")


def _is_xhsish_raw(rec: dict[str, Any]) -> bool:
    if not _is_mediacrawler_raw(rec):
        return False
    plat = str(rec.get("platform") or "").lower()
    name = str(rec.get("source_name") or "")
    return "xhs" in plat or "hongshu" in plat or plat == "xiaohongshu" or "小红书" in name


def _is_mediacrawler_signal(sig: Signal) -> bool:
    return str(sig.raw_source_type or "").startswith("mediacrawler")


def _is_xhsish_signal(sig: Signal) -> bool:
    if not _is_mediacrawler_signal(sig):
        return False
    refs = [r.lower() for r in (sig.platform_refs or [])]
    if any("xhs" in r or "hongshu" in r or r == "xiaohongshu" for r in refs):
        return True
    if sig.source_name and "小红书" in sig.source_name:
        return True
    return False


def log_stage_extract(total_raw: int, extracted: int, *, vision_count: int = 0) -> None:
    logger.info(
        "[intel_hub.pipeline] Layer1+2 内容解析+经营信号抽取 | 原始记录=%d | 成功抽取=%d (%.0f%%)",
        total_raw,
        extracted,
        (extracted / total_raw * 100) if total_raw else 0,
    )
    if vision_count > 0:
        logger.info(
            "[intel_hub.pipeline] Layer1+2 千问VL视觉分析 | 成功=%d / %d 张图笔记",
            vision_count,
            extracted,
        )


def log_stage_collect(raw_records: list[dict[str, Any]]) -> None:
    total = len(raw_records)
    mc = sum(1 for r in raw_records if _is_mediacrawler_raw(r))
    xhs = sum(1 for r in raw_records if _is_xhsish_raw(r))
    other = total - mc
    logger.info(
        "[intel_hub.pipeline] 阶段1 原始数据 | total=%d | mediacrawler=%d (其中小红书平台=%d) | 其他源=%d",
        total,
        mc,
        xhs,
        other,
    )


def log_stage_normalize(
    raw_records: list[dict[str, Any]],
    signals: list[Signal],
    evidence_refs: list[Any],
) -> None:
    raw_n = len(raw_records)
    sig_n = len(signals)
    ev_n = len(evidence_refs)
    dropped = max(0, raw_n - sig_n)
    mc_sig = sum(1 for s in signals if _is_mediacrawler_signal(s))
    xhs_sig = sum(1 for s in signals if _is_xhsish_signal(s))
    logger.info(
        "[intel_hub.pipeline] 阶段2 归一化 | Signal=%d EvidenceRef=%d | 相对原始去重/丢弃约 %d 条 | "
        "mediacrawler信号=%d 小红书平台信号=%d",
        sig_n,
        ev_n,
        dropped,
        mc_sig,
        xhs_sig,
    )


def log_stage_project(signals: list[Signal]) -> None:
    with_entity = sum(1 for s in signals if s.canonical_entity_refs or s.entity_refs)
    tag_counter: Counter[str] = Counter()
    for s in signals:
        for t in s.topic_tags:
            tag_counter[t] += 1
    top = tag_counter.most_common(12)
    top_s = ", ".join(f"{k}:{v}" for k, v in top) if top else "(无)"
    plat_counter: Counter[str] = Counter()
    for s in signals:
        for p in s.platform_refs or []:
            plat_counter[p] += 1
    plat_s = ", ".join(f"{k}:{v}" for k, v in plat_counter.most_common(8)) if plat_counter else "(无)"
    logger.info(
        "[intel_hub.pipeline] Layer3 本体投影 | 带实体引用=%d/%d | platform: %s",
        with_entity,
        len(signals),
        plat_s,
    )
    logger.info("[intel_hub.pipeline] Layer3 topic_tags Top: %s", top_s)

    v2_dims = {
        "scene_refs": sum(1 for s in signals if s.scene_refs),
        "style_refs": sum(1 for s in signals if s.style_refs),
        "need_refs": sum(1 for s in signals if s.need_refs),
        "risk_factor_refs": sum(1 for s in signals if s.risk_factor_refs),
        "material_refs": sum(1 for s in signals if s.material_refs),
        "content_pattern_refs": sum(1 for s in signals if s.content_pattern_refs),
        "visual_pattern_refs": sum(1 for s in signals if s.visual_pattern_refs),
        "audience_refs": sum(1 for s in signals if s.audience_refs),
    }
    dims_s = ", ".join(f"{k}={v}" for k, v in v2_dims.items() if v > 0)
    logger.info("[intel_hub.pipeline] Layer3 V2多维refs: %s", dims_s or "(无命中)")


def log_stage_rank(signals: list[Signal]) -> None:
    if not signals:
        logger.info("[intel_hub.pipeline] 阶段4 打分 | 无信号")
        return
    scores = [s.business_priority_score for s in signals]
    mean = sum(scores) / len(scores)
    top3 = sorted(signals, key=lambda s: s.business_priority_score, reverse=True)[:3]
    lines = []
    for s in top3:
        t = (s.title or "")[:48] + ("…" if len(s.title or "") > 48 else "")
        lines.append(f"score={s.business_priority_score:.3f} | {t}")
    logger.info(
        "[intel_hub.pipeline] 阶段4 打分 | business_priority_score min=%.3f max=%.3f mean=%.3f | Top3:",
        min(scores),
        max(scores),
        mean,
    )
    for line in lines:
        logger.info("[intel_hub.pipeline]   · %s", line)


def log_stage_cluster(
    ranked_signals: list[Signal],
    ontology_mapping: dict[str, Any],
    opportunity_count: int,
    risk_count: int,
    insight_count: int = 0,
    visual_pattern_count: int = 0,
    demand_spec_count: int = 0,
) -> None:
    opp_topics = set(ontology_mapping.get("card_compiler", {}).get("opportunity_topics", []))
    risk_topics = set(ontology_mapping.get("card_compiler", {}).get("risk_topics", []))
    opp_in = [
        s
        for s in ranked_signals
        if opp_topics.intersection(s.topic_tags) and "risk" not in s.topic_tags
    ]
    risk_in = [s for s in ranked_signals if risk_topics.intersection(s.topic_tags)]
    logger.info(
        "[intel_hub.pipeline] Layer4 决策资产编译 | Opportunity=%d Risk=%d Insight=%d VisualPattern=%d DemandSpec=%d",
        opportunity_count,
        risk_count,
        insight_count,
        visual_pattern_count,
        demand_spec_count,
    )
    logger.info(
        "[intel_hub.pipeline] Layer4 | 机会候选信号=%d 风险候选信号=%d | 总信号=%d",
        len(opp_in),
        len(risk_in),
        len(ranked_signals),
    )


def log_stage_persist(storage_path: Any, raw_snapshot_hint: str) -> None:
    logger.info(
        "[intel_hub.pipeline] 持久化 | SQLite=%s | raw 快照=%s",
        storage_path,
        raw_snapshot_hint,
    )
