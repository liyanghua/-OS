"""Single Council specialist turn: SOUL + per-role memory + structured JSON output."""
from __future__ import annotations

import logging
from typing import Any

from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
from apps.content_planning.agents.memory import AgentMemory
from apps.content_planning.agents.soul_loader import SoulLoader

logger = logging.getLogger(__name__)


class CouncilAgentRunner:
    """Run one Council agent turn with SOUL as system slot #1."""

    def __init__(self, memory: AgentMemory, soul_loader: SoulLoader | None = None) -> None:
        self._memory = memory
        self._soul_loader = soul_loader or SoulLoader()

    def opinion(
        self,
        *,
        agent_role: str,
        agent_name: str,
        user_question: str,
        stage: str,
        object_context: str,
        opportunity_id: str,
        prior_statements: list[str],
        council_round: int,
        shared_memory_context: str = "",
        rule_based_fallback: Any = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return (display_text, metadata). rule_based_fallback: callable(role, q, stage) -> str."""
        tagline = self._soul_loader.tagline(agent_role)
        soul = self._soul_loader.load(agent_role)
        mem_block = self._memory.council_memory_block(opportunity_id, agent_role, user_question)
        if shared_memory_context and shared_memory_context.strip() and shared_memory_context != "无历史记忆":
            mem_block = f"{shared_memory_context}\n\n{mem_block}"

        prior_text = "\n".join(prior_statements) if prior_statements else "（本轮尚无其他专家发言。）"
        round_hint = (
            "这是第一轮：请基于独立判断给出立场。"
            if council_round <= 1
            else "这是第二轮：请阅读其他专家第一轮观点，可补充、修正或反驳；说明是否改变立场。"
        )

        if not llm_router.is_any_available():
            text = (rule_based_fallback(agent_role, user_question, stage) if rule_based_fallback else "")
            if not text:
                text = f"作为{agent_name}，建议结合阶段「{stage}」审视该问题。"
            return text, _meta_ok_text(agent_name, stage, tagline, council_round, used_llm=False, degraded=True)

        system_tail = f"""
---
当前阶段（pipeline stage）：{stage}
{round_hint}
你必须只输出一个 JSON 对象（不要 Markdown），格式严格如下：
{{"stance":"support|neutral|oppose|supplement","claim":"一句话立场","detail":"3-5句专业展开","references":["Brief字段或证据键，可选"]}}
stance：support 赞同主方向 / oppose 反对或风险 / supplement 补充条件 / neutral 中立。"""

        system = soul + system_tail

        user_msg = f"""用户问题：
{user_question}

【对象与 Brief 上下文】
{object_context}

【相关记忆】
{mem_block}

【其他专家发言】
{prior_text}

仅输出 JSON。"""

        try:
            resp: dict[str, Any] = llm_router.chat_json(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=user_msg),
                ],
                temperature=0.35,
                max_tokens=4096,
            )
        except Exception:
            logger.warning("council_runner chat_json failed for %s", agent_role, exc_info=True)
            text = (rule_based_fallback(agent_role, user_question, stage) if rule_based_fallback else "")
            if not text:
                text = f"作为{agent_name}，建议结合阶段「{stage}」审视该问题。"
            meta = _meta_ok_text(agent_name, stage, tagline, council_round, used_llm=True, degraded=True)
            return text, meta

        stance = str(resp.get("stance") or "neutral")
        claim = str(resp.get("claim") or "").strip()
        detail = str(resp.get("detail") or "").strip()
        degraded = False
        if not detail:
            detail = (rule_based_fallback(agent_role, user_question, stage) if rule_based_fallback else "")
            if not detail:
                detail = f"作为{agent_name}，建议结合阶段「{stage}」审视该问题。"
            degraded = True
        if not claim:
            claim = detail[:80]
        refs_raw = resp.get("references") or []
        references = [str(x) for x in refs_raw] if isinstance(refs_raw, list) else []
        return detail, {
            "stance": stance,
            "claim": claim,
            "agent_name": agent_name,
            "stage": stage,
            "used_llm": True,
            "degraded": degraded,
            "fallback_mode": "rule_template" if degraded else "",
            "model": "",
            "references": references,
            "soul_tagline": tagline,
            "council_round": council_round,
        }


def _meta_ok_text(
    agent_name: str,
    stage: str,
    tagline: str,
    council_round: int,
    *,
    used_llm: bool,
    degraded: bool,
) -> dict[str, Any]:
    return {
        "stance": "neutral",
        "claim": "",
        "agent_name": agent_name,
        "stage": stage,
        "used_llm": used_llm,
        "degraded": degraded,
        "fallback_mode": "rule_template",
        "model": "",
        "references": [],
        "soul_tagline": tagline,
        "council_round": council_round,
    }
