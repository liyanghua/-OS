"""rule_extractor — SOP MD 表格 → RuleSpec 候选两段式抽取。

第一段：确定性 5 列宽表解析（无 LLM）
第二段：LLM 长句增强（可选；离线 / 无 KEY 时降级为正则规则）

输出全部进入 review.status = 'draft'，等待审核台审核。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from apps.content_planning.schemas.rule_spec import (
    RuleConstraints,
    RuleEvidence,
    RuleLifecycle,
    RuleRecommendation,
    RuleReview,
    RuleScoring,
    RuleSpec,
    RuleTrigger,
)
from apps.content_planning.schemas.source_document import SOPDimension, SourceDocument
from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROMPT_PATH = _REPO_ROOT / "apps" / "content_planning" / "prompts" / "extract_rules.md"


# ── 表格解析 ─────────────────────────────────────────────────


_HEADER_HINT = "变量类别"


def _parse_table(raw_markdown: str) -> list[dict[str, str]]:
    """从 MD 中找到第一张以 `变量类别 | 细分变量 | ...` 为表头的表，返回行 list。

    每行 dict 包含：variable_category / variable_name / option_name / scene / principle
    其中 variable_category 在表格中相邻行可能为空，自动向下继承上一非空值。
    """
    lines = raw_markdown.splitlines()
    rows: list[list[str]] = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                # 表格已结束
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not in_table:
            if any(_HEADER_HINT in c for c in cells):
                in_table = True
                continue
            else:
                continue
        # 跳过分隔行 |---|---|...|
        if all(re.match(r"^[-:\s]+$", c or "-") for c in cells):
            continue
        if len(cells) < 5:
            # 尝试合并尾列
            while len(cells) < 5:
                cells.append("")
        rows.append(cells[:5])

    parsed: list[dict[str, str]] = []
    last_category = ""
    for cells in rows:
        var_cat = cells[0] or last_category
        if cells[0]:
            last_category = cells[0]
        if not cells[1]:
            # 必须有"细分变量"才算一条规则
            continue
        parsed.append(
            {
                "variable_category": var_cat,
                "variable_name": cells[1],
                "option_name": cells[2],
                "scene": cells[3],
                "principle": cells[4],
            }
        )
    return parsed


# ── 启发式抽取（兜底；LLM 失败时使用） ───────────────────────


_AVOID_PATTERNS = [
    r"避免[^。；,，]+[。；]?",
    r"避开[^。；,，]+[。；]?",
    r"切忌[^。；,，]+[。；]?",
    r"严禁[^。；,，]+[。；]?",
    r"不要[^。；,，]+[。；]?",
    r"杜绝[^。；,，]+[。；]?",
    r"杂乱[^。；,，]+[。；]?",
]

_BOOST_PATTERNS = [
    r"优先[^。；,，]+",
    r"更适合[^。；,，]+",
    r"推荐[^。；,，]+",
]

_PENALTY_PATTERNS = [
    r"弱化[^。；,，]+",
    r"减少[^。；,，]+",
    r"慎用[^。；,，]+",
    r"降低[^。；,，]+",
]


def _heuristic_extract(principle: str) -> dict[str, Any]:
    """启发式抽取：从原文用正则提取 must_avoid / boost / penalty。"""
    principle = principle.replace("<br>", " ").strip()

    must_avoid: list[str] = []
    for pat in _AVOID_PATTERNS:
        for m in re.findall(pat, principle):
            cleaned = m.strip("。；").strip()
            if cleaned and cleaned not in must_avoid:
                must_avoid.append(cleaned)

    boost: list[str] = []
    for pat in _BOOST_PATTERNS:
        for m in re.findall(pat, principle):
            cleaned = m.strip().rstrip("。；")
            if cleaned and cleaned not in boost:
                boost.append(cleaned)

    penalty: list[str] = []
    for pat in _PENALTY_PATTERNS:
        for m in re.findall(pat, principle):
            cleaned = m.strip().rstrip("。；")
            if cleaned and cleaned not in penalty:
                penalty.append(cleaned)

    # trigger.conditions: 匹配 "若店铺xxx" / "针对xxx家长"
    conditions: list[str] = []
    for pat in [
        r"若店铺[^。；]+",
        r"店铺[^。；]*主打[^。；]+",
        r"针对[^。；]+家长",
        r"针对[^。；]+人群",
        r"匹配店铺[^。；]+",
    ]:
        for m in re.findall(pat, principle):
            cleaned = m.strip().rstrip("。；")
            if cleaned and cleaned not in conditions:
                conditions.append(cleaned)

    # source_quote 取主原则首句（≤60 字）
    first_sentence = re.split(r"[。；]", principle, maxsplit=1)[0]
    source_quote = first_sentence[:60].strip()

    return {
        "trigger": {
            "conditions": conditions,
            "required_context": [],
        },
        "constraints": {
            "must_follow": [],
            "must_avoid": must_avoid,
        },
        "scoring": {
            "boost_factors": boost,
            "penalty_factors": penalty,
        },
        "evidence": {
            "source_quote": source_quote,
            "confidence": 0.55 if (must_avoid or boost) else 0.4,
        },
    }


# ── LLM 增强 ─────────────────────────────────────────────────


def _read_prompt_template() -> str:
    if not _PROMPT_PATH.exists():
        return ""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _llm_extract(
    *,
    category: str,
    dimension: SOPDimension,
    row: dict[str, str],
    llm_caller: Callable[[str, str], str] | None = None,
) -> dict[str, Any] | None:
    """调用 LLM 抽取；失败返回 None。"""
    template = _read_prompt_template()
    if not template:
        return None

    prompt = template.format(
        category=category,
        dimension=dimension,
        variable_category=row.get("variable_category", ""),
        variable_name=row.get("variable_name", ""),
        option_name=row.get("option_name", ""),
        applicable_scene=row.get("scene", ""),
        matching_principle=row.get("principle", ""),
    )

    if llm_caller is None:
        try:
            from apps.intel_hub.extraction.llm_client import (
                call_text_llm,
                is_llm_available,
                parse_json_response,
            )
        except ImportError:
            return None
        if not is_llm_available():
            return None
        raw = call_text_llm(
            system_prompt="你是专家视觉策略规则抽取器，严格输出 JSON。",
            user_prompt=prompt,
            temperature=0.2,
            max_tokens=1500,
        )
        if not raw:
            return None
        result = parse_json_response(raw)
        return result or None

    raw = llm_caller("你是专家视觉策略规则抽取器，严格输出 JSON。", prompt)
    if not raw:
        return None
    try:
        from apps.intel_hub.extraction.llm_client import parse_json_response
        return parse_json_response(raw) or None
    except ImportError:
        import json
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


# ── 主流程 ────────────────────────────────────────────────────


class RuleExtractor:
    """两段式 RuleSpec 抽取器。"""

    def __init__(
        self,
        store: RuleStore | None = None,
        *,
        llm_caller: Callable[[str, str], str] | None = None,
        use_llm: bool = True,
    ) -> None:
        self.store = store or RuleStore()
        self.llm_caller = llm_caller
        self.use_llm = use_llm

    def extract_from_source(self, source: SourceDocument) -> list[RuleSpec]:
        rows = _parse_table(source.raw_markdown)
        rules: list[RuleSpec] = []
        category = source.category

        for row in rows:
            extracted: dict[str, Any] | None = None
            if self.use_llm:
                extracted = _llm_extract(
                    category=category,
                    dimension=source.dimension,
                    row=row,
                    llm_caller=self.llm_caller,
                )
            if not extracted:
                extracted = _heuristic_extract(row.get("principle", ""))

            rule = self._build_rule(source=source, row=row, extracted=extracted)
            self.store.save_rule_spec(rule.model_dump())
            rules.append(rule)

        # 反查 source_document 更新 extracted_rule_count
        source.extracted_rule_count = len(rules)
        source.parsed_row_count = len(rows)
        self.store.save_source_document(source.model_dump())

        logger.info(
            "[rule_extract] file=%s parsed_rows=%d rules=%d",
            source.file_name, len(rows), len(rules),
        )
        return rules

    def _build_rule(
        self,
        *,
        source: SourceDocument,
        row: dict[str, str],
        extracted: dict[str, Any],
    ) -> RuleSpec:
        trig_data = extracted.get("trigger") or {}
        cons_data = extracted.get("constraints") or {}
        score_data = extracted.get("scoring") or {}
        ev_data = extracted.get("evidence") or {}

        return RuleSpec(
            dimension=source.dimension,
            variable_category=row.get("variable_category", ""),
            variable_name=row.get("variable_name", ""),
            option_name=row.get("option_name", ""),
            category_scope=[source.category] if source.category else [],
            scene_scope=["taobao_main_image"],
            trigger=RuleTrigger(
                conditions=list(trig_data.get("conditions", []) or []),
                required_context=list(trig_data.get("required_context", []) or []),
            ),
            recommendation=RuleRecommendation(
                variable_selection={
                    "variable_category": row.get("variable_category", ""),
                    "variable_name": row.get("variable_name", ""),
                    "option_name": row.get("option_name", ""),
                    "applicable_scene": row.get("scene", ""),
                },
            ),
            constraints=RuleConstraints(
                must_follow=list(cons_data.get("must_follow", []) or []),
                must_avoid=list(cons_data.get("must_avoid", []) or []),
            ),
            scoring=RuleScoring(
                base_weight=0.5,
                boost_factors=list(score_data.get("boost_factors", []) or []),
                penalty_factors=list(score_data.get("penalty_factors", []) or []),
            ),
            evidence=RuleEvidence(
                source_document_id=source.id,
                source_file=source.file_name,
                source_quote=ev_data.get("source_quote", "") or row.get("principle", "")[:60],
                confidence=float(ev_data.get("confidence", 0.5) or 0.5),
            ),
            review=RuleReview(status="draft"),
            lifecycle=RuleLifecycle(),
        )

    def extract_for_category(self, category: str) -> list[RuleSpec]:
        """对指定类目下所有 SourceDocument 执行抽取，返回 RuleSpec 列表。"""
        from apps.content_planning.services.md_ingestion_service import category_to_slug

        slug = category_to_slug(category)
        docs_data = self.store.list_source_documents(category=slug)
        all_rules: list[RuleSpec] = []
        for raw in docs_data:
            doc = SourceDocument(**raw)
            all_rules.extend(self.extract_from_source(doc))
        return all_rules
