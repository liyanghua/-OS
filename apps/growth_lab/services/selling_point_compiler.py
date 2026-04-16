"""SellingPointCompilerService：从 TrendOpportunity 列表编译结构化卖点对象。

架构：LLM 三阶段编译（洞察提炼→卖点构建→平台表达）+ SSE 实时推送 + 规则兜底。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator

from apps.growth_lab.schemas.selling_point_spec import (
    PlatformExpressionSpec,
    SellingPointSpec,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
    logger.addHandler(_h)

CompileEvent = dict[str, Any]

_SYSTEM_PROMPT = """\
你是一个电商卖点编译专家。给定一组趋势机会数据，你需要提炼出结构化卖点规格。

请输出严格 JSON（不要 markdown code fence），字段如下：
{
  "core_claim": "一句话核心卖点主张",
  "supporting_claims": ["辅助卖点1", "辅助卖点2"],
  "target_people": ["目标人群1", "目标人群2"],
  "target_scenarios": ["目标场景1", "目标场景2"],
  "differentiation_notes": "差异化说明",
  "shelf_expression": {
    "headline": "货架标题",
    "sub_copy": "副标题",
    "visual_direction": "视觉方向",
    "tone": "表达语气"
  },
  "first3s_expression": {
    "headline": "前3秒钩子文案",
    "sub_copy": "辅助文案",
    "visual_direction": "视觉方向",
    "tone": "表达语气"
  }
}

要求：
- core_claim 必须凝练、直击用户痛点
- supporting_claims 2-4 条，与核心主张互补
- target_people / target_scenarios 各 2-3 条
- differentiation_notes 说明与竞品的差异
- shelf_expression 面向电商货架场景
- first3s_expression 面向短视频前3秒
"""


class SellingPointCompilerService:
    """LLM 优先 + 规则兜底的卖点编译器。"""

    async def compile(
        self,
        opportunities: list[dict],
        *,
        workspace_id: str = "",
        brand_id: str = "",
    ) -> SellingPointSpec:
        """从一组机会 dict 编译出 SellingPointSpec。"""
        opp_ids = [o.get("opportunity_id", "") for o in opportunities if o.get("opportunity_id")]

        llm_spec = await self._try_llm_compile(opportunities, opp_ids, workspace_id, brand_id)
        if llm_spec is not None:
            return llm_spec

        logger.info("LLM 编译不可用或失败，降级到规则提取")
        return self._rule_based_compile(opportunities, opp_ids, workspace_id, brand_id)

    # ── SSE 三阶段编译 ──

    async def compile_stream(
        self,
        opportunities: list[dict],
        *,
        workspace_id: str = "",
        brand_id: str = "",
        expert_annotations: list[dict] | None = None,
    ) -> AsyncGenerator[CompileEvent, None]:
        """三阶段 SSE 编译流：洞察提炼 → 卖点构建 → 平台表达。"""
        opp_ids = [o.get("opportunity_id", "") for o in opportunities if o.get("opportunity_id")]
        user_content = self._build_user_content(opportunities, expert_annotations=expert_annotations)

        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            yield {"event": "compile_stage", "stage": "error", "data": {"message": "LLM 不可用，降级到规则提取"}}
            result = self._rule_based_compile(opportunities, opp_ids, workspace_id, brand_id)
            yield {"event": "compile_complete", "data": result.model_dump()}
            return

        # Stage 1: 洞察提炼
        yield {"event": "compile_stage", "stage": "insight", "status": "running", "data": {"label": "洞察提炼", "description": "分析机会信号，提取核心痛点与需求…"}}
        t0 = time.perf_counter()
        stage1_prompt = (
            "你是电商洞察分析专家。请根据以下机会数据，提炼出核心洞察。\n"
            "直接输出纯 JSON（不要用 markdown code fence，不要加 ```json 包裹，不要输出思考过程）：\n"
            '{"insight_summary": "一段话总结核心发现", '
            '"key_pain_points": ["痛点1","痛点2"], '
            '"key_desires": ["需求1","需求2"], '
            '"market_signals": ["信号1","信号2"], '
            '"reasoning": "你的分析思路（1-2句话）"}\n\n'
        )
        _s1_fallback = {"insight_summary": "（分析降级）", "key_pain_points": [], "key_desires": [], "reasoning": "LLM 返回为空或调用失败"}
        try:
            s1_msgs = [LLMMessage(role="system", content=stage1_prompt), LLMMessage(role="user", content=user_content)]
            logger.info("[Stage1] prompt.system 长度=%d, prompt.user 长度=%d", len(stage1_prompt), len(user_content))
            resp1 = await llm_router.achat(s1_msgs, temperature=0.3, max_tokens=3000)
            logger.info("[Stage1] model=%s provider=%s elapsed=%dms finish=%s content_len=%d",
                        resp1.model, resp1.provider, resp1.elapsed_ms, resp1.finish_reason, len(resp1.content or ""))
            logger.info("[Stage1] raw_content=\n%s", resp1.content)
            stage1_data = self._safe_json_parse(resp1.content)
            if not stage1_data.get("insight_summary"):
                logger.warning("[Stage1] 解析后无 insight_summary → 降级兜底")
                stage1_data = _s1_fallback
            else:
                logger.info("[Stage1] 解析成功: keys=%s", list(stage1_data.keys()))
        except Exception:
            logger.warning("[Stage1] 异常", exc_info=True)
            stage1_data = _s1_fallback

        elapsed1 = int((time.perf_counter() - t0) * 1000)
        yield {"event": "compile_stage", "stage": "insight", "status": "done", "elapsed_ms": elapsed1, "data": stage1_data}

        # Stage 2: 卖点构建
        yield {"event": "compile_stage", "stage": "selling_point", "status": "running", "data": {"label": "卖点构建", "description": "构建核心主张与支撑论据，匹配人群场景…"}}
        t1 = time.perf_counter()
        stage2_prompt = (
            "你是电商卖点编译专家。基于以下洞察和原始数据，构建结构化卖点。\n"
            "直接输出纯 JSON（不要用 markdown code fence，不要加 ```json 包裹，不要输出思考过程）：\n"
            '{"core_claim": "一句话核心卖点", '
            '"supporting_claims": ["辅助卖点1","辅助卖点2"], '
            '"target_people": ["人群1","人群2"], '
            '"target_scenarios": ["场景1","场景2"], '
            '"differentiation_notes": "差异化说明", '
            '"reasoning": "你的构建思路（1-2句话）"}\n\n'
            f"### 洞察分析结果\n{json.dumps(stage1_data, ensure_ascii=False)}\n\n"
        )
        titles = [o.get("title", "") for o in opportunities if o.get("title")]
        _s2_fallback = {"core_claim": titles[0] if titles else "待编辑", "supporting_claims": [], "target_people": [], "target_scenarios": [], "reasoning": "LLM 返回为空或调用失败"}
        try:
            s2_msgs = [LLMMessage(role="system", content=stage2_prompt), LLMMessage(role="user", content=user_content)]
            logger.info("[Stage2] prompt.system 长度=%d, prompt.user 长度=%d", len(stage2_prompt), len(user_content))
            resp2 = await llm_router.achat(s2_msgs, temperature=0.4, max_tokens=3000)
            logger.info("[Stage2] model=%s provider=%s elapsed=%dms finish=%s content_len=%d",
                        resp2.model, resp2.provider, resp2.elapsed_ms, resp2.finish_reason, len(resp2.content or ""))
            logger.info("[Stage2] raw_content=\n%s", resp2.content)
            stage2_data = self._safe_json_parse(resp2.content)
            if not stage2_data.get("core_claim"):
                logger.warning("[Stage2] 解析后无 core_claim → 降级兜底")
                stage2_data = _s2_fallback
            else:
                logger.info("[Stage2] 解析成功: core_claim=%r, keys=%s", stage2_data.get("core_claim", "")[:50], list(stage2_data.keys()))
        except Exception:
            logger.warning("[Stage2] 异常", exc_info=True)
            stage2_data = _s2_fallback

        elapsed2 = int((time.perf_counter() - t1) * 1000)
        yield {"event": "compile_stage", "stage": "selling_point", "status": "done", "elapsed_ms": elapsed2, "data": stage2_data}

        # Stage 3: 平台表达
        yield {"event": "compile_stage", "stage": "expression", "status": "running", "data": {"label": "平台表达", "description": "生成货架文案与前3秒钩子…"}}
        t2 = time.perf_counter()
        stage3_prompt = (
            "你是电商文案和短视频创意专家。基于以下卖点，生成平台表达。\n"
            "直接输出纯 JSON（不要用 markdown code fence，不要加 ```json 包裹，不要输出思考过程）：\n"
            '{"shelf_expression": {"headline": "货架标题", "sub_copy": "副标题", "visual_direction": "视觉方向", "tone": "语气"}, '
            '"first3s_expression": {"headline": "前3秒钩子", "sub_copy": "辅助文案", "visual_direction": "视觉方向", "tone": "语气"}, '
            '"reasoning": "你的创意思路（1-2句话）"}\n\n'
            f"### 卖点规格\n核心主张: {stage2_data.get('core_claim', '')}\n"
            f"支撑论据: {', '.join(stage2_data.get('supporting_claims', []))}\n"
            f"目标人群: {', '.join(stage2_data.get('target_people', []))}\n"
            f"目标场景: {', '.join(stage2_data.get('target_scenarios', []))}\n"
        )
        _expr_fallback = {
            "shelf_expression": {"headline": stage2_data.get("core_claim", "")[:30], "sub_copy": "", "visual_direction": "", "tone": "利益点突出"},
            "first3s_expression": {"headline": stage2_data.get("core_claim", "")[:20] + "？", "sub_copy": "", "visual_direction": "痛点场景切入", "tone": "悬念/共鸣"},
            "reasoning": "LLM 返回为空或调用失败，使用兜底文案",
        }
        try:
            s3_msgs = [LLMMessage(role="system", content=stage3_prompt), LLMMessage(role="user", content=user_content[:500])]
            logger.info("[Stage3] prompt.system 长度=%d, prompt.user 长度=%d", len(stage3_prompt), len(user_content[:500]))
            resp3 = await llm_router.achat(s3_msgs, temperature=0.5, max_tokens=3000)
            logger.info("[Stage3] model=%s provider=%s elapsed=%dms finish=%s content_len=%d",
                        resp3.model, resp3.provider, resp3.elapsed_ms, resp3.finish_reason, len(resp3.content or ""))
            logger.info("[Stage3] raw_content=\n%s", resp3.content)
            stage3_data = self._safe_json_parse(resp3.content)
            if not stage3_data.get("shelf_expression") and not stage3_data.get("first3s_expression"):
                logger.warning("[Stage3] 解析后无 expression 数据 → 降级兜底 (parsed_keys=%s)", list(stage3_data.keys()))
                stage3_data = _expr_fallback
            else:
                logger.info("[Stage3] 解析成功: has_shelf=%s, has_first3s=%s",
                            bool(stage3_data.get("shelf_expression")), bool(stage3_data.get("first3s_expression")))
        except Exception:
            logger.warning("[Stage3] 异常", exc_info=True)
            stage3_data = _expr_fallback

        elapsed3 = int((time.perf_counter() - t2) * 1000)
        yield {"event": "compile_stage", "stage": "expression", "status": "done", "elapsed_ms": elapsed3, "data": stage3_data}

        # 组装最终结果
        shelf_raw = stage3_data.get("shelf_expression", {})
        first3s_raw = stage3_data.get("first3s_expression", {})

        shelf_expr = None
        if isinstance(shelf_raw, dict) and shelf_raw.get("headline"):
            shelf_expr = PlatformExpressionSpec(platform="shelf", expression_type="shelf", **{k: shelf_raw.get(k, "") for k in ("headline", "sub_copy", "visual_direction", "tone")})

        first3s_expr = None
        if isinstance(first3s_raw, dict) and first3s_raw.get("headline"):
            first3s_expr = PlatformExpressionSpec(platform="douyin", expression_type="first3s", **{k: first3s_raw.get(k, "") for k in ("headline", "sub_copy", "visual_direction", "tone")})

        result = SellingPointSpec(
            source_opportunity_ids=opp_ids,
            core_claim=str(stage2_data.get("core_claim", "")).strip(),
            supporting_claims=[str(s) for s in stage2_data.get("supporting_claims", []) if s],
            target_people=[str(p) for p in stage2_data.get("target_people", []) if p],
            target_scenarios=[str(s) for s in stage2_data.get("target_scenarios", []) if s],
            differentiation_notes=str(stage2_data.get("differentiation_notes", "")),
            shelf_expression=shelf_expr,
            first3s_expression=first3s_expr,
            confidence_score=0.7,
            workspace_id=workspace_id,
            brand_id=brand_id,
            status="compiled",
        )

        from apps.growth_lab.services.selling_point_evaluator import SellingPointEvaluator
        evaluator = SellingPointEvaluator()
        evaluation = evaluator.evaluate(result.model_dump())

        yield {"event": "compile_complete", "data": result.model_dump(), "evaluation": evaluation}

    @staticmethod
    def _safe_json_parse(text: str | None) -> dict:
        """从 LLM 响应中宽松解析 JSON。

        处理：纯 JSON、markdown code fence 包裹、<think> 标签包裹、
        以及 max_tokens 截断导致的不完整 JSON。
        """
        if not text or not text.strip():
            return {}
        import re

        cleaned = text.strip()

        # 去除 Qwen 思考标签
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned).strip()
        # 去除未闭合的 <think> 标签（被截断时）
        cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned).strip()

        # 提取 markdown code fence 中的内容
        fence_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        elif cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:]).strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        # 尝试直接解析
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 括号匹配提取最外层 JSON 对象
        m = re.search(r"\{", cleaned)
        if m:
            depth, start = 0, m.start()
            last_close = -1
            for i in range(start, len(cleaned)):
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                    if depth == 0:
                        last_close = i
                        break
            if last_close > start:
                try:
                    return json.loads(cleaned[start:last_close + 1])
                except json.JSONDecodeError:
                    pass

            # 截断修复：尝试补全不完整 JSON
            if last_close == -1 and depth > 0:
                fragment = cleaned[start:]
                for _ in range(depth):
                    fragment += "}"
                try:
                    result = json.loads(fragment)
                    logger.warning("_safe_json_parse: 补全 %d 个缺失的 '}'", depth)
                    return result
                except json.JSONDecodeError:
                    pass

        return {}

    # ── LLM 路径 ──

    async def _try_llm_compile(
        self,
        opportunities: list[dict],
        opp_ids: list[str],
        workspace_id: str,
        brand_id: str,
    ) -> SellingPointSpec | None:
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return None

        user_content = self._build_user_content(opportunities)
        messages = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        try:
            data = llm_router.chat_json(messages, temperature=0.4, max_tokens=2000)
            if not data:
                return None
            return self._parse_llm_response(data, opp_ids, workspace_id, brand_id)
        except Exception:
            logger.debug("LLM 卖点编译失败，将降级到规则提取", exc_info=True)
            return None

    @staticmethod
    def _build_user_content(
        opportunities: list[dict],
        *,
        expert_annotations: list[dict] | None = None,
    ) -> str:
        lines = ["以下是机会数据列表，请提炼卖点：\n"]
        for i, opp in enumerate(opportunities[:10], 1):
            title = opp.get("title", "未知")
            summary = opp.get("summary", "")
            topics = ", ".join(opp.get("linked_topics", [])[:5])
            scenarios = ", ".join(opp.get("linked_scenarios", [])[:5])
            people = ", ".join(opp.get("linked_people", [])[:5])
            actions = ", ".join(opp.get("suggested_actions", [])[:3])
            lines.append(
                f"### 机会 {i}: {title}\n"
                f"- 摘要: {summary}\n"
                f"- 话题: {topics}\n"
                f"- 场景: {scenarios}\n"
                f"- 人群: {people}\n"
                f"- 建议动作: {actions}\n"
            )

            ctx = opp.get("rich_context", {})
            if ctx:
                if ctx.get("pain_point"):
                    lines.append(f"- 用户痛点: {ctx['pain_point']}")
                if ctx.get("desire"):
                    lines.append(f"- 用户诉求: {ctx['desire']}")
                if ctx.get("hook"):
                    lines.append(f"- 内容钩子: {ctx['hook']}")
                if ctx.get("selling_points"):
                    lines.append(f"- 已有卖点线索: {', '.join(ctx['selling_points'][:5])}")
                if ctx.get("content_angle"):
                    lines.append(f"- 内容角度: {ctx['content_angle']}")
                if ctx.get("why_now"):
                    lines.append(f"- 为何现在做: {ctx['why_now']}")
                if ctx.get("why_worth_doing"):
                    lines.append(f"- 值得做的原因: {ctx['why_worth_doing']}")
                if ctx.get("insight_statement"):
                    lines.append(f"- 洞察: {ctx['insight_statement']}")
                if ctx.get("engagement_insight"):
                    lines.append(f"- 互动洞察: {ctx['engagement_insight']}")
                if ctx.get("action_recommendation"):
                    lines.append(f"- 行动建议: {ctx['action_recommendation']}")
                lines.append("")

        if expert_annotations:
            lines.append("\n---\n### 专家经验参考\n")
            for ann in expert_annotations[:10]:
                ann_type_map = {"insight": "洞察补充", "correction": "方向纠偏", "risk": "风险提示", "template": "经验模板"}
                label = ann_type_map.get(ann.get("annotation_type", ""), "参考")
                lines.append(f"- 【{label}】{ann.get('field_name', '')}: {ann.get('content', '')}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _parse_llm_response(
        data: dict[str, Any],
        opp_ids: list[str],
        workspace_id: str,
        brand_id: str,
    ) -> SellingPointSpec | None:
        core = data.get("core_claim")
        if not core or not isinstance(core, str):
            return None

        shelf_raw = data.get("shelf_expression")
        first3s_raw = data.get("first3s_expression")

        shelf_expr = None
        if isinstance(shelf_raw, dict) and shelf_raw.get("headline"):
            shelf_expr = PlatformExpressionSpec(
                platform="shelf",
                expression_type="shelf",
                headline=shelf_raw.get("headline", ""),
                sub_copy=shelf_raw.get("sub_copy", ""),
                visual_direction=shelf_raw.get("visual_direction", ""),
                tone=shelf_raw.get("tone", ""),
            )

        first3s_expr = None
        if isinstance(first3s_raw, dict) and first3s_raw.get("headline"):
            first3s_expr = PlatformExpressionSpec(
                platform="douyin",
                expression_type="first3s",
                headline=first3s_raw.get("headline", ""),
                sub_copy=first3s_raw.get("sub_copy", ""),
                visual_direction=first3s_raw.get("visual_direction", ""),
                tone=first3s_raw.get("tone", ""),
            )

        supporting = data.get("supporting_claims", [])
        if not isinstance(supporting, list):
            supporting = []

        return SellingPointSpec(
            source_opportunity_ids=opp_ids,
            core_claim=core.strip(),
            supporting_claims=[str(s) for s in supporting if s],
            target_people=[str(p) for p in data.get("target_people", []) if p],
            target_scenarios=[str(s) for s in data.get("target_scenarios", []) if s],
            differentiation_notes=str(data.get("differentiation_notes", "")),
            shelf_expression=shelf_expr,
            first3s_expression=first3s_expr,
            confidence_score=0.7,
            workspace_id=workspace_id,
            brand_id=brand_id,
            status="compiled",
        )

    # ── 规则兜底 ──

    @staticmethod
    def _rule_based_compile(
        opportunities: list[dict],
        opp_ids: list[str],
        workspace_id: str,
        brand_id: str,
    ) -> SellingPointSpec:
        titles = [o.get("title", "") for o in opportunities if o.get("title")]
        core_claim = titles[0] if titles else "待编辑卖点"

        supporting: list[str] = []
        people: list[str] = []
        scenarios: list[str] = []
        for opp in opportunities:
            supporting.extend(opp.get("linked_topics", [])[:2])
            people.extend(opp.get("linked_people", [])[:2])
            scenarios.extend(opp.get("linked_scenarios", [])[:2])

        supporting = list(dict.fromkeys(supporting))[:4]
        people = list(dict.fromkeys(people))[:3]
        scenarios = list(dict.fromkeys(scenarios))[:3]

        shelf_expr = PlatformExpressionSpec(
            platform="shelf",
            expression_type="shelf",
            headline=core_claim[:30],
            sub_copy="｜".join(supporting[:2]) if supporting else "",
            tone="利益点突出",
        )

        first3s_expr = PlatformExpressionSpec(
            platform="douyin",
            expression_type="first3s",
            headline=core_claim[:20] + "？" if core_claim else "你知道吗？",
            sub_copy="｜".join(supporting[:2]) if supporting else "",
            visual_direction="痛点场景切入",
            tone="悬念/共鸣",
        )

        return SellingPointSpec(
            source_opportunity_ids=opp_ids,
            core_claim=core_claim,
            supporting_claims=supporting,
            target_people=people,
            target_scenarios=scenarios,
            differentiation_notes="规则提取，建议人工补充差异化说明",
            shelf_expression=shelf_expr,
            first3s_expression=first3s_expr,
            confidence_score=0.3,
            workspace_id=workspace_id,
            brand_id=brand_id,
            status="draft",
        )
