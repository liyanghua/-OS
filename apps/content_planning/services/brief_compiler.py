"""BriefCompiler：从 promoted 机会卡提炼 OpportunityBrief。"""

from __future__ import annotations

from typing import Any

from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.intel_hub.projector.label_zh import to_zh, to_zh_list
from apps.intel_hub.schemas.opportunity import XHSOpportunityCard


_GOAL_MAP: dict[str, str] = {
    "visual": "种草收藏",
    "scene": "种草收藏",
    "demand": "转化",
    "product": "转化",
    "content": "展示种草",
}

_TEMPLATE_HINT_MAP: dict[str, list[str]] = {
    "种草收藏": ["scene_seed", "style_anchor"],
    "转化": ["budget_hero", "texture_proof"],
    "展示种草": ["scene_seed", "style_anchor", "texture_proof"],
}


class BriefCompiler:
    """规则优先的 Brief 编译器，逐字段从机会卡提取。"""

    def compile(
        self,
        card: XHSOpportunityCard,
        parsed_note: dict[str, Any] | None = None,
        review_summary: dict[str, Any] | None = None,
    ) -> OpportunityBrief:
        note_context = (parsed_note or {}).get("note_context", {})
        cross_modal_dict = (parsed_note or {}).get("cross_modal_validation", {})
        selling_signals_dict = (parsed_note or {}).get("selling_theme_signals", {})

        content_goal = self._infer_content_goal(card, review_summary, note_context, cross_modal_dict)
        proofs = self._extract_proof(card)
        evidence_summary = self._build_evidence_summary(card, review_summary)
        constraints = self._extract_constraints(card, review_summary)
        suggested_direction = self._build_suggested_direction(card, review_summary)

        if review_summary:
            proofs = self._enrich_proof_from_reviews(proofs, review_summary)

        brief = OpportunityBrief(
            opportunity_id=card.opportunity_id,
            source_note_ids=list(card.source_note_ids),
            brief_status="generated",
            opportunity_type=to_zh(card.opportunity_type),
            opportunity_title=card.title,
            opportunity_summary=card.summary,
            target_user=to_zh_list(self._extract_target_user(card)),
            target_scene=to_zh_list(self._extract_target_scene(card)),
            core_motive=to_zh(self._extract_core_motive(card) or ""),
            content_goal=content_goal,
            target_audience=self._build_target_audience(card),
            evidence_summary=evidence_summary,
            constraints=constraints,
            suggested_direction=suggested_direction,
            primary_value=to_zh(self._extract_primary_value(card) or ""),
            secondary_values=to_zh_list(self._extract_secondary_values(card)),
            visual_style_direction=to_zh_list(self._extract_visual_direction(card)),
            price_positioning=to_zh(self._extract_price_positioning(card, parsed_note) or ""),
            template_hints=to_zh_list(self._generate_template_hints(card, content_goal)),
            avoid_directions=to_zh_list(self._extract_avoid_directions(card)),
            proof_from_source=proofs,
            why_worth_doing=self._build_why_worth_doing(card, note_context, cross_modal_dict, review_summary),
            competitive_angle=self._build_competitive_angle(cross_modal_dict, selling_signals_dict),
            engagement_proof=self._build_engagement_proof(note_context),
            cross_modal_confidence_label=self._build_cross_modal_confidence_label(cross_modal_dict),
        )

        brief.opportunity_title = self._zh_replace_refs(brief.opportunity_title or "")
        brief.opportunity_summary = self._zh_replace_refs(brief.opportunity_summary or "")

        return brief

    @staticmethod
    def _extract_target_scene(card: XHSOpportunityCard) -> list[str]:
        scenes: list[str] = []
        scenes.extend(card.scene_refs[:5])
        for tag in card.entity_refs[:3]:
            if any(kw in tag for kw in ("场景", "桌", "餐", "茶", "聚", "早")):
                scenes.append(tag)
        return list(dict.fromkeys(scenes))[:6]

    @staticmethod
    def _extract_target_user(card: XHSOpportunityCard) -> list[str]:
        users: list[str] = []
        users.extend(card.audience_refs[:5])
        for ref in card.need_refs[:3]:
            if any(kw in ref for kw in ("人群", "用户", "宝妈", "上班族", "学生", "租房")):
                users.append(ref)
        return list(dict.fromkeys(users))[:6]

    @staticmethod
    def _extract_core_motive(card: XHSOpportunityCard) -> str | None:
        if card.need_refs:
            return card.need_refs[0]
        if card.summary:
            return card.summary[:60]
        return None

    @staticmethod
    def _infer_content_goal(
        card: XHSOpportunityCard,
        review_summary: dict[str, Any] | None = None,
        note_context: dict[str, Any] | None = None,
        cross_modal_dict: dict[str, Any] | None = None,
    ) -> str:
        base = _GOAL_MAP.get(card.opportunity_type, "种草收藏")
        tags: list[str] = []

        if review_summary:
            avg = review_summary.get("avg_quality_score") or 0
            if avg >= 9.0:
                tags.append("高质量机会")

        if note_context:
            like = note_context.get("like_count", 0) or 0
            collect = note_context.get("collect_count", 0) or 0
            comment = note_context.get("comment_count", 0) or 0
            total = like + collect + comment + (note_context.get("share_count", 0) or 0)
            if like > 0 and collect / max(like, 1) >= 0.8:
                tags.append("收藏驱动")
            if total > 0 and comment / max(total, 1) >= 0.1:
                tags.append("讨论驱动")

        if cross_modal_dict:
            score = cross_modal_dict.get("overall_consistency_score")
            if score is not None and score >= 0.7:
                tags.append("已验证")

        if tags:
            return f"{base}（{'、'.join(tags)}）"
        return base

    @staticmethod
    def _build_target_audience(card: XHSOpportunityCard) -> str | None:
        parts = [to_zh(r) for r in card.audience_refs[:3]]
        if not parts:
            return None
        return "、".join(parts)

    @staticmethod
    def _build_evidence_summary(
        card: XHSOpportunityCard,
        review_summary: dict[str, Any] | None,
    ) -> str | None:
        parts: list[str] = []
        if card.evidence_refs:
            parts.append(f"共 {len(card.evidence_refs)} 条证据")
        if review_summary:
            rc = review_summary.get("review_count", 0)
            avg = review_summary.get("avg_quality_score")
            if rc:
                parts.append(f"已检视 {rc} 次")
            if avg is not None:
                parts.append(f"平均质量 {avg:.1f}/10")
        return "；".join(parts) if parts else None

    @staticmethod
    def _extract_constraints(
        card: XHSOpportunityCard,
        review_summary: dict[str, Any] | None,
    ) -> list[str]:
        constraints: list[str] = []
        constraints.extend(to_zh(r) for r in card.risk_refs[:3])
        if review_summary:
            for note in review_summary.get("latest_notes", [])[:3]:
                if note and len(note) > 5:
                    constraints.append(f"检视备注: {note[:80]}")
        return constraints[:5]

    @staticmethod
    def _build_suggested_direction(
        card: XHSOpportunityCard,
        review_summary: dict[str, Any] | None,
    ) -> str | None:
        if card.suggested_next_step:
            step = card.suggested_next_step
            if isinstance(step, list):
                return "；".join(step[:2])
            return str(step)[:120]
        return None

    @staticmethod
    def _enrich_proof_from_reviews(
        proofs: list[str],
        review_summary: dict[str, Any],
    ) -> list[str]:
        for note in review_summary.get("latest_notes", [])[:2]:
            if note and note not in proofs:
                proofs.append(f"[检视] {note[:150]}")
        return proofs[:8]

    @staticmethod
    def _extract_primary_value(card: XHSOpportunityCard) -> str | None:
        if card.value_proposition_refs:
            return card.value_proposition_refs[0]
        if card.need_refs:
            return card.need_refs[0]
        return None

    @staticmethod
    def _extract_secondary_values(card: XHSOpportunityCard) -> list[str]:
        vals: list[str] = []
        vals.extend(card.value_proposition_refs[1:4])
        vals.extend(card.need_refs[1:3])
        return list(dict.fromkeys(vals))[:5]

    @staticmethod
    def _extract_visual_direction(card: XHSOpportunityCard) -> list[str]:
        dirs: list[str] = []
        dirs.extend(card.style_refs[:4])
        dirs.extend(card.visual_pattern_refs[:3])
        return list(dict.fromkeys(dirs))[:6]

    @staticmethod
    def _extract_price_positioning(
        card: XHSOpportunityCard,
        parsed_note: dict[str, Any] | None,
    ) -> str | None:
        for ref in card.need_refs + card.entity_refs:
            if any(kw in ref for kw in ("平价", "性价比", "高端", "轻奢", "便宜", "贵")):
                return ref
        if parsed_note:
            price_info = parsed_note.get("selling_theme_signals", {}).get("price_tier")
            if price_info:
                return str(price_info)
        return None

    @staticmethod
    def _generate_template_hints(card: XHSOpportunityCard, content_goal: str | None) -> list[str]:
        hints = _TEMPLATE_HINT_MAP.get(content_goal or "", [])
        if card.opportunity_type == "visual":
            hints = list(dict.fromkeys(["style_anchor", "texture_proof"] + hints))
        if card.opportunity_type == "scene":
            hints = list(dict.fromkeys(["scene_seed", "occasion_gift"] + hints))
        return hints[:4]

    @staticmethod
    def _extract_avoid_directions(card: XHSOpportunityCard) -> list[str]:
        avoids: list[str] = []
        avoids.extend(card.risk_refs[:3])
        return avoids

    @staticmethod
    def _extract_proof(card: XHSOpportunityCard) -> list[str]:
        proofs: list[str] = []
        for ev in card.evidence_refs[:5]:
            snippet = getattr(ev, "snippet", "") or getattr(ev, "text", "")
            if snippet:
                proofs.append(str(snippet)[:200])
        return proofs

    # ── 策划层洞察方法 ──────────────────────────────

    @staticmethod
    def _build_why_worth_doing(
        card: XHSOpportunityCard,
        note_context: dict[str, Any] | None,
        cross_modal_dict: dict[str, Any] | None,
        review_summary: dict[str, Any] | None,
    ) -> str | None:
        fragments: list[str] = []

        if note_context:
            like = note_context.get("like_count", 0) or 0
            collect = note_context.get("collect_count", 0) or 0
            total = like + collect + (note_context.get("comment_count", 0) or 0) + (note_context.get("share_count", 0) or 0)
            if total > 500:
                cl_ratio = round(collect / max(like, 1), 2)
                if cl_ratio >= 0.8:
                    fragments.append(f"笔记藏赞比 {cl_ratio}，具备强收藏驱动力")
                elif total > 1000:
                    fragments.append(f"笔记互动量 {total}，市场关注度高")

        if cross_modal_dict:
            high = cross_modal_dict.get("high_confidence_claims", [])
            total_claims = len(high) + len(cross_modal_dict.get("unsupported_claims", [])) + len(cross_modal_dict.get("challenged_claims", []))
            if total_claims > 0:
                ratio = len(high) / total_claims
                if ratio >= 0.6:
                    fragments.append(f"核心卖点 {len(high)}/{total_claims} 经多维验证")
                else:
                    fragments.append(f"卖点验证率 {len(high)}/{total_claims}，需聚焦已验证方向")

        if review_summary:
            avg = review_summary.get("avg_quality_score")
            if avg is not None and avg >= 8.0:
                fragments.append(f"人工检视评分 {avg:.1f}/10")

        direction = _GOAL_MAP.get(card.opportunity_type, "种草收藏")
        if fragments:
            return f"{'，'.join(fragments)} → {direction}内容有明确潜力"
        return None

    @staticmethod
    def _build_competitive_angle(
        cross_modal_dict: dict[str, Any] | None,
        selling_signals_dict: dict[str, Any] | None,
    ) -> str | None:
        if not cross_modal_dict and not selling_signals_dict:
            return None

        verified: list[str] = []
        caution: list[str] = []

        if cross_modal_dict:
            verified.extend(cross_modal_dict.get("high_confidence_claims", [])[:3])
            caution.extend(cross_modal_dict.get("challenged_claims", [])[:2])
            caution.extend(cross_modal_dict.get("unsupported_claims", [])[:2])

        if not verified and selling_signals_dict:
            verified.extend(selling_signals_dict.get("validated_selling_points", [])[:3])

        if not verified and not caution:
            return None

        parts: list[str] = []
        if verified:
            parts.append(f"围绕「{'、'.join(verified[:3])}」做差异化")
        if caution:
            parts.append(f"谨慎使用「{'、'.join(caution[:3])}」（待验证）")

        return "；".join(parts) if parts else None

    @staticmethod
    def _build_engagement_proof(note_context: dict[str, Any] | None) -> str | None:
        if not note_context:
            return None
        like = note_context.get("like_count", 0) or 0
        collect = note_context.get("collect_count", 0) or 0
        comment = note_context.get("comment_count", 0) or 0
        share = note_context.get("share_count", 0) or 0
        total = like + collect + comment + share
        if total == 0:
            return None

        cl_ratio = round(collect / max(like, 1), 2)
        comment_rate = round(comment / max(total, 1) * 100, 1)

        if cl_ratio >= 1.0:
            content_type = "高收藏型内容"
        elif cl_ratio >= 0.5:
            content_type = "中等收藏型内容"
        elif comment_rate >= 10:
            content_type = "讨论型内容"
        else:
            content_type = "一般互动内容"

        return f"原笔记 {collect} 收藏 / {like} 赞 / 藏赞比 {cl_ratio} / 评论率 {comment_rate}%，属{content_type}"

    @staticmethod
    def _build_cross_modal_confidence_label(cross_modal_dict: dict[str, Any] | None) -> str | None:
        if not cross_modal_dict:
            return None
        score = cross_modal_dict.get("overall_consistency_score")
        if score is None:
            return None

        unsupported_count = len(cross_modal_dict.get("unsupported_claims", []))
        challenged_count = len(cross_modal_dict.get("challenged_claims", []))
        issue_count = unsupported_count + challenged_count

        if score >= 0.7:
            label = f"高置信（一致性 {score:.2f}）"
        elif score >= 0.4:
            suffix = f"，{issue_count} 项待验证" if issue_count else ""
            label = f"中置信（一致性 {score:.2f}{suffix}）"
        else:
            label = f"低置信（一致性 {score:.2f}，{issue_count} 项不支持）"
        return label

    @staticmethod
    def _zh_replace_refs(text: str) -> str:
        """将文本中嵌入的英文本体 ref ID（scene_*, style_*, need_* 等）替换为中文。"""
        import re
        if not text:
            return text
        ref_pattern = re.compile(r"\b((?:scene|style|need|risk|audience|visual|material|content_pattern)_[\w]+)")
        return ref_pattern.sub(lambda m: to_zh(m.group(1)), text)
