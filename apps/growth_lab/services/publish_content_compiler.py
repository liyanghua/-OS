"""PublishContentCompiler: LLM 生成小红书发布内容（标题+正文+话题）。

基于卖点规格、钩子脚本、专家批注生成高质量小红书笔记文案，
失败时 fallback 到 xhs_publisher.build_publish_content() 规则拼接。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一位资深小红书爆款笔记运营，擅长用口语化、有节奏感的文案撰写短视频笔记。

任务：基于给定的卖点规格和视频钩子脚本，生成一条小红书视频笔记的发布内容。

【输出格式】直接输出纯 JSON，禁止使用 ```json``` 包裹，禁止输出思考过程：
{"title": "...", "body": "...", "topics": ["...", "..."]}

【字段要求】
title（最多20字）：
- 必须抓眼球，善用数字、反问、对比、悬念
- 紧扣核心卖点，不要泛泛而谈

body（150-300字，严格不超过300字）：
- 第一段（最重要）：直击核心卖点，用一两句话让读者立刻感知产品最大的价值
- 第二段：展开1-2个支撑卖点，用体验感受来表达
- 第三段：行动号召（CTA），引导互动
- 风格：口语化、像和朋友分享，用\\n换行，每段1-3句
- emoji：每段最多1个，克制使用

topics（3-5个话题标签）：
- 贴近小红书热门话题风格，不加#号
"""


class PublishContentCompiler:
    """LLM 驱动的小红书发布内容生成器。"""

    async def compile(
        self,
        hook_script: dict[str, Any],
        spec: dict[str, Any] | None = None,
        annotations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """生成 {title, body, topics}。LLM 失败时抛异常，由调用方 fallback。"""
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            raise RuntimeError("LLM router not available")

        user_content = self._build_user_content(hook_script, spec, annotations)
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        resp = await llm_router.achat(messages, temperature=0.7, max_tokens=2000)
        logger.info(
            "[PublishCompiler] model=%s elapsed=%dms content_len=%d",
            resp.model, resp.elapsed_ms, len(resp.content or ""),
        )

        parsed = self._safe_json_parse(resp.content)
        if not parsed.get("title"):
            raise ValueError(f"LLM output missing title: {resp.content[:200]}")

        title = str(parsed["title"])[:20]
        body = str(parsed.get("body", ""))
        topics = parsed.get("topics", [])
        if isinstance(topics, list):
            topics = [str(t).strip().lstrip("#") for t in topics if t][:5]
        else:
            topics = []

        return {"title": title, "body": body, "topics": topics}

    @staticmethod
    def _build_user_content(
        hook_script: dict[str, Any],
        spec: dict[str, Any] | None,
        annotations: list[dict[str, Any]] | None,
    ) -> str:
        parts: list[str] = []

        if spec:
            parts.append("## 卖点规格")
            parts.append(f"核心主张：{spec.get('core_claim', '')}")
            claims = spec.get("supporting_claims", [])
            if claims:
                parts.append(f"支撑主张：{'、'.join(claims)}")
            people = spec.get("target_people", [])
            if people:
                parts.append(f"目标人群：{'、'.join(people)}")
            scenarios = spec.get("target_scenarios", [])
            if scenarios:
                parts.append(f"目标场景：{'、'.join(scenarios)}")
            diff = spec.get("differentiation_notes", "")
            if diff:
                parts.append(f"差异化说明：{diff}")

            exprs = spec.get("platform_expressions", [])
            if isinstance(exprs, list):
                for expr in exprs:
                    if expr.get("expression_type") == "first3s":
                        parts.append(f"\n前3秒表达方向：")
                        parts.append(f"  标题：{expr.get('headline', '')}")
                        parts.append(f"  副文案：{expr.get('sub_copy', '')}")
                        parts.append(f"  视觉方向：{expr.get('visual_direction', '')}")
                        parts.append(f"  语气：{expr.get('tone', '')}")
                        break

        parts.append("\n## 视频钩子脚本")
        parts.append(f"开场白：{hook_script.get('opening_line', '')}")
        parts.append(f"支撑句：{hook_script.get('supporting_line', '')}")
        parts.append(f"行动号召：{hook_script.get('cta_line', '')}")
        tone = hook_script.get("tone", "")
        if tone:
            parts.append(f"语气：{tone}")

        if annotations:
            parts.append("\n## 专家批注")
            for ann in annotations[:5]:
                atype = ann.get("annotation_type", "")
                field = ann.get("field_name", "")
                content = ann.get("content", "")
                if content:
                    parts.append(f"- [{atype}] {field}：{content}")

        parts.append("\n请基于以上信息，生成小红书视频笔记的发布内容。")
        return "\n".join(parts)

    @staticmethod
    def _safe_json_parse(text: str | None) -> dict:
        if not text or not text.strip():
            return {}
        cleaned = text.strip()

        # Strip <think>...</think> wrapper
        think_match = re.search(r"</think>\s*(.*)", cleaned, re.DOTALL)
        if think_match:
            cleaned = think_match.group(1).strip()

        # Strip closed code fence
        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        else:
            # Handle unclosed fence (LLM output truncated before closing ```)
            open_fence = re.match(r"```(?:json)?\s*\n?(.*)", cleaned, re.DOTALL)
            if open_fence:
                cleaned = open_fence.group(1).strip()

        def _try_loads(s: str) -> dict | None:
            """json.loads with fallback: escape raw newlines inside string values."""
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
            # LLM often emits literal newlines inside JSON strings; escape them
            escaped = re.sub(
                r'(?<=": ")(.*?)(?="[,\s\}])',
                lambda m: m.group(0).replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"),
                s, flags=re.DOTALL,
            )
            if escaped != s:
                try:
                    return json.loads(escaped)
                except json.JSONDecodeError:
                    pass
            return None

        result = _try_loads(cleaned)
        if result is not None:
            return result

        # Extract substring from first { to last }
        brace_start = cleaned.find("{")
        if brace_start == -1:
            return {}
        fragment = cleaned[brace_start:]
        brace_end = fragment.rfind("}")
        if brace_end > 0:
            result = _try_loads(fragment[:brace_end + 1])
            if result is not None:
                return result

        # Truncated JSON: try to repair by closing open quotes and braces
        repaired = PublishContentCompiler._repair_truncated_json(fragment)
        if repaired:
            result = _try_loads(repaired)
            if result is not None:
                return result

        return {}

    @staticmethod
    def _repair_truncated_json(fragment: str) -> str | None:
        """Best-effort repair of JSON truncated mid-stream."""
        if not fragment or not fragment.startswith("{"):
            return None

        in_string = False
        escape_next = False
        depth = 0

        for ch in fragment:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                if in_string:
                    escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1

        suffix = ""
        if in_string:
            suffix += '"'
        suffix += "}" * max(depth, 1)
        return fragment + suffix
