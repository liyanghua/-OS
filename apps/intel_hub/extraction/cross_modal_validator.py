"""跨模态一致性校验器 —— 检查视觉/文本/评论间的一致性。

不做信号提取，只检查已有三维信号之间的一致性，
输出 high_confidence / unsupported / challenged claims。
"""

from __future__ import annotations

from apps.intel_hub.schemas.evidence import XHSEvidenceRef
from apps.intel_hub.schemas.xhs_parsed import XHSParsedNote
from apps.intel_hub.schemas.xhs_signals import SceneSignals, SellingThemeSignals, VisualSignals
from apps.intel_hub.schemas.xhs_validation import CrossModalValidation

# 卖点 -> 对应的视觉信号关键词映射
SELLING_VISUAL_MAP: dict[str, list[str]] = {
    "防水": ["防水展示", "防水", "泼水", "水珠"],
    "防油": ["防油展示", "防油"],
    "出片": ["出片", "出片感展示", "氛围感", "氛围图"],
    "显高级": ["高级感展示", "高级感", "高级感呈现", "质感"],
    "好打理": ["好打理", "易清洁"],
    "贴合": ["贴合桌面展示", "贴合", "平整"],
    "厚实": ["厚重", "厚实"],
    "颜值高": ["出片", "氛围感", "高级感呈现"],
    "材质有质感": ["有纹理", "材质纹理展示"],
    "易铺平": ["贴合桌面展示", "贴合"],
    "尺寸适配": ["尺寸适配展示"],
    "平价": [],
}

# 场景标题词 -> 视觉场景词映射
SCENE_VISUAL_MAP: dict[str, list[str]] = {
    "出租屋": ["出租屋场景", "出租屋"],
    "餐桌": ["餐桌场景", "餐桌"],
    "茶几": ["茶几场景", "茶几"],
    "书桌": ["书桌场景", "书桌"],
    "宿舍": ["宿舍场景", "宿舍"],
    "拍照布景": ["拍照布景", "拍照"],
}


def validate_visual_support(
    selling_points: list[str],
    visual: VisualSignals,
) -> tuple[dict[str, bool | str], list[XHSEvidenceRef]]:
    """检查文本卖点是否被视觉信号支持。

    Returns:
        (selling_claim_visual_support, evidence_refs)
    """
    all_visual = set(
        visual.visual_feature_highlights
        + visual.visual_expression_pattern
        + visual.visual_texture_signals
        + visual.visual_style_signals
    )
    all_visual_lower = {v.lower() for v in all_visual}

    support: dict[str, bool | str] = {}
    evidence: list[XHSEvidenceRef] = []

    for sp in selling_points:
        visual_kws = SELLING_VISUAL_MAP.get(sp, [])
        if not visual_kws:
            support[sp] = "uncertain"
            continue

        found = any(vk.lower() in all_visual_lower or vk.lower() in " ".join(all_visual).lower() for vk in visual_kws)
        support[sp] = found

        if found:
            evidence.append(XHSEvidenceRef(
                source_kind="image",
                source_ref=f"{visual.note_id}:visual_support",
                snippet=f"卖点'{sp}'有视觉支持",
                confidence=0.7,
            ))
        else:
            evidence.append(XHSEvidenceRef(
                source_kind="image",
                source_ref=f"{visual.note_id}:visual_gap",
                snippet=f"卖点'{sp}'缺乏视觉支持",
                confidence=0.5,
            ))

    return support, evidence


def validate_comment_support(
    selling_points: list[str],
    validated: list[str],
    challenges: list[str],
    purchase_intent: list[str],
    trust_gap: list[str],
) -> dict[str, bool | str]:
    """检查文本卖点是否被评论验证或质疑。

    Returns:
        selling_claim_comment_validation
    """
    result: dict[str, bool | str] = {}

    challenge_text = " ".join(challenges).lower()
    trust_text = " ".join(trust_gap).lower()

    for sp in selling_points:
        sp_lower = sp.lower()

        if sp in validated:
            result[sp] = True
            continue

        is_challenged = any(sp_lower in c.lower() for c in challenges) or sp_lower in challenge_text
        is_doubted = any(sp_lower in t.lower() for t in trust_gap) or sp_lower in trust_text

        if is_challenged or is_doubted:
            result[sp] = False
        else:
            result[sp] = "uncertain"

    return result


def validate_scene_alignment(
    scene_signals: SceneSignals,
    visual: VisualSignals,
    title: str,
    body: str,
) -> tuple[dict[str, bool | str], list[XHSEvidenceRef]]:
    """检查场景在标题/图片/评论间是否一致。

    Returns:
        (scene_alignment, evidence_refs)
    """
    alignment: dict[str, bool | str] = {}
    evidence: list[XHSEvidenceRef] = []

    visual_scene_set = {s.lower().replace("场景", "") for s in visual.visual_scene_signals}
    title_lower = title.lower()
    body_lower = body.lower()

    for scene in scene_signals.scene_signals:
        scene_lower = scene.lower().replace("场景", "")
        visual_kws = SCENE_VISUAL_MAP.get(scene, [scene])

        in_visual = any(vk.lower().replace("场景", "") in " ".join(visual_scene_set) for vk in visual_kws) or scene_lower in " ".join(visual_scene_set)
        in_title = scene_lower in title_lower

        key = f"scene_{scene}_alignment"
        if in_title and in_visual:
            alignment[key] = True
            evidence.append(XHSEvidenceRef(
                source_kind="title",
                source_ref=scene_signals.note_id,
                snippet=f"场景'{scene}'标题和视觉一致",
                confidence=0.8,
            ))
        elif in_title or in_visual:
            alignment[key] = "partial"
        else:
            alignment[key] = "uncertain"

    if scene_signals.scene_signals and visual.visual_scene_signals:
        alignment["title_scene_matches_visual_scene"] = any(
            s.lower().replace("场景", "") in " ".join(visual_scene_set)
            for s in scene_signals.scene_signals
        )

    return alignment, evidence


def validate_cross_modal_consistency(
    visual: VisualSignals,
    selling: SellingThemeSignals,
    scene: SceneSignals,
    note: XHSParsedNote,
) -> CrossModalValidation:
    """跨模态一致性校验总入口。"""
    all_sp = selling.selling_point_signals or (selling.primary_selling_points + selling.secondary_selling_points)

    visual_support, vs_ev = validate_visual_support(all_sp, visual)

    comment_validation = validate_comment_support(
        all_sp,
        selling.validated_selling_points,
        selling.selling_point_challenges,
        selling.purchase_intent_signals,
        selling.trust_gap_signals,
    )

    scene_alignment, sa_ev = validate_scene_alignment(
        scene, visual, note.normalized_title, note.normalized_body,
    )

    high_conf: list[str] = []
    unsupported: list[str] = []
    challenged: list[str] = []

    for sp in all_sp:
        vs = visual_support.get(sp, "uncertain")
        cv = comment_validation.get(sp, "uncertain")

        if vs is True and cv is True:
            high_conf.append(sp)
        elif vs is True and cv != False:
            high_conf.append(sp)
        elif cv is True and vs != False:
            high_conf.append(sp)
        elif cv is False:
            challenged.append(sp)
        elif vs is False and cv == "uncertain":
            unsupported.append(sp)
        elif vs == "uncertain" and cv == "uncertain":
            unsupported.append(sp)

    total_checks = len(all_sp) + len(scene_alignment)
    positive = sum(1 for v in visual_support.values() if v is True)
    positive += sum(1 for v in comment_validation.values() if v is True)
    positive += sum(1 for v in scene_alignment.values() if v is True)

    consistency_score = round(positive / max(total_checks, 1), 2)

    all_evidence = vs_ev + sa_ev

    return CrossModalValidation(
        note_id=note.note_id,
        selling_claim_visual_support=visual_support,
        selling_claim_comment_validation=comment_validation,
        scene_alignment=scene_alignment,
        overall_consistency_score=consistency_score,
        unsupported_claims=unsupported,
        challenged_claims=challenged,
        high_confidence_claims=high_conf,
        evidence_refs=all_evidence,
    )
