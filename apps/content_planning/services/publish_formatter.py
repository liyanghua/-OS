"""XHS 发布格式化器：将 AssetBundle 转为可直接发布的小红书笔记内容包。"""

from __future__ import annotations

import logging
import re

from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.compilation_report import PublishReadyPackage
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy

logger = logging.getLogger(__name__)

_XHS_TITLE_MAX_LEN = 20
_XHS_BODY_MAX_LEN = 1000
_XHS_MAX_HASHTAGS = 10
_XHS_MAX_TOPICS = 3

_EMOJI_INSERTS = {
    "kind": ["✨", "💫", "🌟"],
    "scene": ["🏠", "☕", "🍽️", "🌿"],
    "product": ["🎁", "💝", "🛒"],
    "quality": ["👍", "💯", "⭐"],
}


class XHSPublishFormatter:
    """从 AssetBundle + Strategy 组装 PublishReadyPackage。"""

    def format(
        self,
        bundle: AssetBundle,
        strategy: RewriteStrategy | None = None,
    ) -> PublishReadyPackage:
        title, title_rationale = self._select_best_title(bundle.title_candidates)
        body = self._format_body(bundle.body_draft, bundle.body_outline, strategy)
        cover_prompt, image_prompts = self._build_image_prompts(bundle.image_execution_briefs)
        hashtags = self._extract_hashtags(strategy, bundle)
        topics = self._extract_topics(strategy, bundle)

        return PublishReadyPackage(
            asset_bundle_id=bundle.asset_bundle_id,
            platform="xhs",
            selected_title=title,
            title_rationale=title_rationale,
            final_body=body,
            cover_image_prompt=cover_prompt,
            image_prompts=image_prompts,
            hashtags=hashtags[:_XHS_MAX_HASHTAGS],
            topic_tags=topics[:_XHS_MAX_TOPICS],
            character_count=len(body),
            source_opportunity_id=bundle.opportunity_id,
            template_id=bundle.template_id,
            strategy_id=bundle.strategy_id,
            plan_id=bundle.plan_id,
        )

    @staticmethod
    def _select_best_title(candidates: list[dict]) -> tuple[str, str]:
        if not candidates:
            return "未生成标题", ""

        scored: list[tuple[float, dict]] = []
        for c in candidates:
            text = c.get("title_text", "")
            if not text:
                continue
            score = 0.0
            length = len(text)
            if 8 <= length <= _XHS_TITLE_MAX_LEN:
                score += 2.0
            elif length <= 6:
                score += 0.5
            else:
                score += 1.0

            if "｜" in text or "|" in text:
                score += 1.0
            if any(ch in text for ch in "！？✨💫🌟"):
                score += 0.5
            if c.get("rationale"):
                score += 0.3

            scored.append((score, c))

        if not scored:
            return candidates[0].get("title_text", "未生成标题"), ""

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        return best.get("title_text", ""), best.get("rationale", "")

    @staticmethod
    def _format_body(
        body_draft: str,
        body_outline: list[str],
        strategy: RewriteStrategy | None,
    ) -> str:
        if not body_draft and not body_outline:
            return ""

        text = body_draft or "\n".join(body_outline)

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        formatted_parts: list[str] = []
        for i, para in enumerate(paragraphs):
            if i == 0 and not any(para.startswith(ch) for ch in "✨💫🌟☀️❤️"):
                para = "✨ " + para
            elif len(para) < 30 and not para.startswith(("#", "—", "·")):
                para = "📌 " + para
            formatted_parts.append(para)

        if strategy and strategy.cta_strategy:
            cta = strategy.cta_strategy.strip()
            if not any(cta in p for p in formatted_parts):
                formatted_parts.append("")
                formatted_parts.append(f"👉 {cta}")

        body = "\n\n".join(formatted_parts)

        if len(body) > _XHS_BODY_MAX_LEN:
            body = body[:_XHS_BODY_MAX_LEN - 3] + "..."

        return body

    @staticmethod
    def _build_image_prompts(
        briefs: list,
    ) -> tuple[str, list[str]]:
        if not briefs:
            return "", []

        prompts: list[str] = []
        for item in briefs:
            if isinstance(item, dict):
                parts = []
                if item.get("role"):
                    parts.append(f"[{item['role']}]")
                if item.get("subject"):
                    parts.append(item["subject"])
                if item.get("composition"):
                    parts.append(f"构图: {item['composition']}")
                if item.get("color_mood"):
                    parts.append(f"色调: {item['color_mood']}")
                if item.get("props"):
                    parts.append(f"道具: {', '.join(item['props'][:5])}")
                if item.get("text_overlay"):
                    parts.append(f"文字: {item['text_overlay']}")
                prompts.append(" | ".join(parts))
            else:
                parts = []
                if getattr(item, "role", ""):
                    parts.append(f"[{item.role}]")
                if getattr(item, "subject", ""):
                    parts.append(item.subject)
                if getattr(item, "composition", ""):
                    parts.append(f"构图: {item.composition}")
                if getattr(item, "color_mood", ""):
                    parts.append(f"色调: {item.color_mood}")
                if getattr(item, "props", []):
                    parts.append(f"道具: {', '.join(item.props[:5])}")
                if getattr(item, "text_overlay", ""):
                    parts.append(f"文字: {item.text_overlay}")
                prompts.append(" | ".join(parts))

        cover = prompts[0] if prompts else ""
        return cover, prompts

    @staticmethod
    def _extract_hashtags(
        strategy: RewriteStrategy | None,
        bundle: AssetBundle,
    ) -> list[str]:
        tags: list[str] = []

        if strategy:
            for field in (strategy.scene_emphasis, strategy.title_strategy, strategy.body_strategy):
                for item in field:
                    words = re.findall(r"[\u4e00-\u9fff]+", item)
                    for w in words:
                        if 2 <= len(w) <= 8:
                            tag = f"#{w}"
                            if tag not in tags:
                                tags.append(tag)

        if bundle.template_name:
            tags.append(f"#{bundle.template_name}")

        defaults = ["#家居好物", "#桌布推荐", "#氛围感"]
        for d in defaults:
            if d not in tags:
                tags.append(d)

        return tags

    @staticmethod
    def _extract_topics(
        strategy: RewriteStrategy | None,
        bundle: AssetBundle,
    ) -> list[str]:
        topics: list[str] = []
        if strategy and strategy.positioning_statement:
            words = re.findall(r"[\u4e00-\u9fff]{2,6}", strategy.positioning_statement)
            for w in words[:2]:
                topics.append(w)
        if not topics:
            topics = ["家居好物分享", "桌面改造"]
        return topics
