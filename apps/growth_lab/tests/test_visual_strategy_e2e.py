"""SOP 视觉策略编译器 端到端冒烟 + service 单测。

覆盖：
- strategy_compiler：6 archetype 输出 + rule_refs 回链 + 评分顺序
- visual_brief_compiler：候选 → CreativeBrief 回填 candidate.creative_brief_id
- visual_prompt_compiler：CreativeBrief → 中文 positive/negative + 比例参数
- weight_updater：仅 expert_score.overall 调权 + history 落库
- feedback_engine：自动从 candidate.rule_refs 回填 rule_ids 后调权
- 端到端冒烟：MD → RuleSpec → 审核 → RulePack → ContextSpec → StrategyPack → Brief → PromptSpec → Feedback → 权重更新

使用临时 sqlite 隔离，单测互不污染；不依赖真实 LLM。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.content_planning.schemas.context_spec import ContextSpec
from apps.content_planning.schemas.source_document import SourceDocument
from apps.content_planning.services.context_compiler import ContextCompiler
from apps.content_planning.services.rule_extractor import RuleExtractor
from apps.content_planning.services.rule_review_service import RuleReviewService
from apps.content_planning.services.rulepack_builder import RulePackBuilder
from apps.content_planning.storage.rule_store import RuleStore
from apps.growth_lab.schemas.feedback_record import FeedbackRecord
from apps.growth_lab.services.feedback_engine import FeedbackEngine
from apps.growth_lab.services.strategy_compiler import StrategyCompiler
from apps.growth_lab.services.visual_brief_compiler import VisualBriefCompiler
from apps.growth_lab.services.visual_prompt_compiler import VisualPromptCompiler
from apps.growth_lab.services.weight_updater import WeightUpdater
from apps.growth_lab.storage.visual_strategy_store import VisualStrategyStore


# 6 个维度各一行，保证 archetype 都有规则可挑
_FULL_MD_BY_DIM = {
    "visual_core": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 主体物 | 桌垫 | 实拍俯视图 | 淘宝主图 | 必须真实呈现产品全貌；避免过度滤镜；优先突出 防水 等核心卖点。 |
""",
    "people_interaction": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 人物 | 儿童使用 | 儿童俯身画画 | 淘宝主图 | 优先呈现真实使用场景；必须保留儿童面部正向情绪；避免穿戴杂乱。 |
""",
    "function_selling_point": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 卖点 | 防水耐磨 | 水珠测试演示 | 淘宝主图 | 优先突出 防水 的差异点；避免抽象广告语；必须可视化体现。 |
""",
    "pattern_style": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 图案 | 卡通主题 | 莫兰迪低饱和 | 淘宝主图 | 优先 莫兰迪 等温柔色调；避免高饱和荧光色；必须与品牌主色协调。 |
""",
    "marketing_info": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 营销 | 价格信息 | 限时直降 | 淘宝主图 | 优先突出 直降 强度；避免堆叠多种价格元素；必须可读性高。 |
""",
    "differentiation": """| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 差异化 | 防滑底 | 边角防滑特写 | 淘宝主图 | 优先 防滑底 差异化能力；避免与竞品同质化；必须特写呈现细节。 |
""",
}


# ── fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def stores(tmp_path: Path):
    rs = RuleStore(db_path=tmp_path / "rule.sqlite")
    vs = VisualStrategyStore(db_path=tmp_path / "growth.sqlite")
    return rs, vs


@pytest.fixture()
def seeded_pack(stores):
    """造一个完整的 active RulePack，含 6 个维度各 1 条 approved 规则。"""
    rs, _ = stores
    extractor = RuleExtractor(store=rs, use_llm=False)
    review = RuleReviewService(store=rs)

    for dim, md in _FULL_MD_BY_DIM.items():
        doc = SourceDocument(
            category="children_desk_mat",
            title=f"6大维度·{dim}",
            file_name=f"{dim}.md",
            file_path=f"assets/SOP/儿童桌垫/{dim}.md",
            dimension=dim,  # type: ignore[arg-type]
            raw_markdown=md,
            status="parsed",
        )
        rs.save_source_document(doc.model_dump())
        rules = extractor.extract_from_source(doc)
        for r in rules:
            review.review(r.id, action="approve", reviewer="qa_bot")

    builder = RulePackBuilder(store=rs)
    pack = builder.build(category="children_desk_mat")
    return pack


@pytest.fixture()
def context(stores) -> ContextSpec:
    rs, _ = stores
    compiler = ContextCompiler(store=rs)
    return compiler.compile_manual(
        category="children_desk_mat",
        scene="taobao_main_image",
        product={"name": "护眼桌垫 60×40", "category": "children_desk_mat", "claims": ["防水", "耐磨"]},
        store_visual={"style": "暖色温馨", "colors": ["奶油白", "原木色"], "image_tone": "明亮自然光"},
        audience={"buyer": "宝妈", "user": "幼儿园儿童"},
        brand_profile={"workspace_id": "ws_01", "brand_id": "brd_01"},
    )


# ── strategy_compiler ────────────────────────────────────────────


def _load_candidates(vs, pack):
    return [vs.get_strategy_candidate(cid) for cid in pack.candidate_ids]


def test_strategy_compiler_outputs_archetypes_with_rule_refs(stores, seeded_pack, context) -> None:
    rs, vs = stores
    compiler = StrategyCompiler(rule_store=rs, visual_strategy_store=vs)
    pack = compiler.compile(context=context, rule_pack=seeded_pack)

    candidates = _load_candidates(vs, pack)
    # archetype 数量与 RulePack.default_strategy_archetypes 对齐
    assert len(candidates) == len(seeded_pack.default_strategy_archetypes)
    assert len(candidates) >= 1

    # 每个候选 rule_refs 必填，total 在 [0, 10]
    for cand in candidates:
        assert cand is not None
        assert cand.get("rule_refs"), f"archetype={cand.get('archetype')} 缺少 rule_refs 回链"
        assert 0.0 <= float(cand["score"]["total"]) <= 10.0

    # 持久化
    persisted = vs.get_visual_strategy_pack(pack.id)
    assert persisted is not None


# ── visual_brief_compiler ────────────────────────────────────────


def test_brief_compiler_writes_creative_brief_id_back(stores, seeded_pack, context) -> None:
    rs, vs = stores
    sc = StrategyCompiler(rule_store=rs, visual_strategy_store=vs)
    pack = sc.compile(context=context, rule_pack=seeded_pack)
    candidates = _load_candidates(vs, pack)
    cand_dict = candidates[0]

    bc = VisualBriefCompiler(store=vs)
    brief = bc.compile(candidate=cand_dict, context=context)

    assert brief.id
    assert brief.strategy_candidate_id == cand_dict["id"]
    assert brief.canvas.ratio == "1:1"  # taobao_main_image
    assert brief.canvas.platform == "taobao_main_image"

    # 回写候选
    saved_cand = vs.get_strategy_candidate(cand_dict["id"])
    assert saved_cand is not None
    assert saved_cand["creative_brief_id"] == brief.id


# ── visual_prompt_compiler ───────────────────────────────────────


def test_prompt_compiler_chinese_only_with_workflow_reserved(stores, seeded_pack, context) -> None:
    rs, vs = stores
    pack = StrategyCompiler(rule_store=rs, visual_strategy_store=vs).compile(
        context=context, rule_pack=seeded_pack
    )
    candidates = _load_candidates(vs, pack)
    brief = VisualBriefCompiler(store=vs).compile(candidate=candidates[0], context=context)

    pc = VisualPromptCompiler(store=vs)
    spec = pc.compile(brief=brief, provider="comfyui")

    assert spec.creative_brief_id == brief.id
    assert spec.provider == "comfyui"
    assert spec.positive_prompt_zh, "中文 positive 必填"
    assert "画面比例" in spec.positive_prompt_zh
    assert spec.positive_prompt_en == ""
    assert spec.negative_prompt_en == ""
    assert spec.workflow_json == {}, "MVP 阶段 workflow_json 留空"
    assert spec.generation_params.width > 0
    assert spec.generation_params.height > 0


# ── weight_updater v0.1 ──────────────────────────────────────────


def test_weight_updater_only_expert_score(stores, seeded_pack) -> None:
    rs, _ = stores
    rule_id = seeded_pack.rule_ids[0]
    before = rs.get_rule_spec(rule_id)
    assert before is not None
    before_w = float(before["scoring"]["base_weight"])

    wu = WeightUpdater(rule_store=rs)
    history = wu.update_from_expert_score(
        feedback_record={
            "id": "fb_001",
            "rule_ids": [rule_id],
            "expert_score": {"overall": 8.0},
        },
    )
    assert len(history) == 1
    after = rs.get_rule_spec(rule_id)
    assert after is not None
    after_w = float(after["scoring"]["base_weight"])
    assert after_w > before_w, "高分应使权重升高"
    assert after_w <= 1.0

    # 业务指标 v0.1 不调权
    biz_history = wu.update_from_business_metrics(
        feedback_record={"id": "fb_002", "rule_ids": [rule_id]},
    )
    assert biz_history == []


# ── feedback_engine ──────────────────────────────────────────────


def test_feedback_engine_backfills_rule_ids(stores, seeded_pack, context) -> None:
    rs, vs = stores
    pack = StrategyCompiler(rule_store=rs, visual_strategy_store=vs).compile(
        context=context, rule_pack=seeded_pack
    )
    candidates = _load_candidates(vs, pack)
    cand_id = candidates[0]["id"]

    record = FeedbackRecord(
        strategy_candidate_id=cand_id,
        decision="enter_test_pool",
        expert_score={"overall": 9.0},  # type: ignore[arg-type]
        comments="冒烟测试",
    )
    engine = FeedbackEngine(visual_strategy_store=vs, rule_store=rs)
    result = engine.submit(record)

    assert result["feedback_record"]["strategy_candidate_id"] == cand_id
    # rule_ids 应自动从 candidate.rule_refs 回填
    assert result["feedback_record"]["rule_ids"], "应自动回填 rule_ids"
    assert result["weight_history"], "高分应触发权重更新"


# ── 端到端冒烟 ───────────────────────────────────────────────────


def test_end_to_end_smoke_children_desk_mat(stores, seeded_pack, context) -> None:
    """PRD 第十七节 v0.1：6 MD → 候选 → Brief → Prompt → 评分回流。"""
    rs, vs = stores

    # 1) 编译策略包
    sc = StrategyCompiler(rule_store=rs, visual_strategy_store=vs)
    pack = sc.compile(context=context, rule_pack=seeded_pack)
    candidates = _load_candidates(vs, pack)
    assert len(candidates) >= 1
    chosen = candidates[0]
    assert chosen["rule_refs"]

    # 2) 候选 → CreativeBrief
    brief = VisualBriefCompiler(store=vs).compile(candidate=chosen, context=context)
    assert brief.canvas.ratio == "1:1"

    # 3) Brief → PromptSpec
    spec = VisualPromptCompiler(store=vs).compile(brief=brief)
    assert spec.positive_prompt_zh

    # 4) 评分回流
    record = FeedbackRecord(
        strategy_candidate_id=chosen["id"],
        decision="enter_test_pool",
        expert_score={"overall": 8.5},  # type: ignore[arg-type]
    )
    res = FeedbackEngine(visual_strategy_store=vs, rule_store=rs).submit(record)
    assert res["weight_history"], "评分应触发至少一条权重更新"

    # 5) 权重历史可查
    rule_id = chosen["rule_refs"][0]
    history = rs.list_rule_weight_history(rule_id)
    assert history and history[0]["delta"] != 0.0
