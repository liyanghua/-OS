"""SOP 视觉策略编译器 Phase 1-3 单元测试。

覆盖：
- rule_extractor：表格解析 + 启发式抽取（不依赖真实 LLM）
- rule_review_service：通过 / 拒绝 / 调权
- rulepack_builder：聚合 approved → active RulePack
- context_compiler：手动 ContextSpec 组装

使用临时 sqlite 隔离，单测互不污染。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.content_planning.schemas.source_document import SourceDocument
from apps.content_planning.services.context_compiler import ContextCompiler
from apps.content_planning.services.rule_extractor import RuleExtractor
from apps.content_planning.services.rule_review_service import RuleReviewService
from apps.content_planning.services.rulepack_builder import RulePackBuilder
from apps.content_planning.storage.rule_store import RuleStore


_SAMPLE_MD = """# 6大维度·42个细分变量选择逻辑01

| 变量类别 | 细分变量 | 可选组合 | 适配场景 | 匹配原则与方法 |
| --- | --- | --- | --- | --- |
| 主体物 | 桌垫 | 实拍俯视图 | 淘宝主图 | 必须真实呈现产品全貌；避免过度滤镜；优先突出 防水耐磨 等核心卖点。 |
| 背景 | 桌面环境 | 浅木纹纯色 | 淘宝主图 | 与品牌主色协调；避免出现杂乱学习用品；可加少量绘画类道具营造氛围。 |
"""


# ── fixtures ───────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> RuleStore:
    return RuleStore(db_path=tmp_path / "rule.sqlite")


@pytest.fixture()
def source_doc(store: RuleStore) -> SourceDocument:
    doc = SourceDocument(
        category="children_desk_mat",
        title="6大维度·42个细分变量选择逻辑01",
        file_name="6大维度·42个细分变量选择逻辑01.md",
        file_path="assets/SOP/儿童桌垫/6大维度·42个细分变量选择逻辑01.md",
        dimension="visual_core",
        raw_markdown=_SAMPLE_MD,
        status="parsed",
    )
    store.save_source_document(doc.model_dump())
    return doc


# ── rule_extractor ────────────────────────────────────────────────

def test_rule_extractor_table_parse_and_save(store: RuleStore, source_doc: SourceDocument) -> None:
    extractor = RuleExtractor(store=store, use_llm=False)
    rules = extractor.extract_from_source(source_doc)

    assert len(rules) == 2, "两行表格应该产出两条 RuleSpec"
    persisted = store.list_rule_specs(category="children_desk_mat")
    assert len(persisted) == 2

    sample = rules[0]
    assert sample.dimension == "visual_core"
    assert sample.category_scope == ["children_desk_mat"]
    assert sample.scene_scope == ["taobao_main_image"]
    assert sample.review.status == "draft"
    # 启发式抽取应至少把"避免"项收入 must_avoid
    if "过度滤镜" in sample.evidence.source_quote:
        assert any("过度滤镜" in s for s in sample.constraints.must_avoid), \
            "启发式应识别 '避免...' 句式 → must_avoid"


# ── rule_review_service ───────────────────────────────────────────

def test_rule_review_approve_and_update_weight(store: RuleStore, source_doc: SourceDocument) -> None:
    extractor = RuleExtractor(store=store, use_llm=False)
    rules = extractor.extract_from_source(source_doc)
    rule_id = rules[0].id

    review = RuleReviewService(store=store)
    updated = review.review(rule_id, action="approve", reviewer="qa_bot")
    assert updated is not None
    assert updated.review.status == "approved"
    assert updated.lifecycle.status == "active"

    weighted = review.review(rule_id, action="update_weight", new_weight=0.82)
    assert weighted is not None
    assert weighted.scoring.base_weight == pytest.approx(0.82)


def test_rule_review_reject_marks_deprecated(store: RuleStore, source_doc: SourceDocument) -> None:
    extractor = RuleExtractor(store=store, use_llm=False)
    rules = extractor.extract_from_source(source_doc)
    rule_id = rules[0].id

    review = RuleReviewService(store=store)
    rejected = review.review(rule_id, action="reject", reviewer="qa_bot", comments="不适用本类目")
    assert rejected is not None
    assert rejected.review.status == "rejected"
    assert rejected.lifecycle.status == "deprecated"


# ── rulepack_builder ──────────────────────────────────────────────

def test_rulepack_builder_aggregates_approved_rules(store: RuleStore, source_doc: SourceDocument) -> None:
    extractor = RuleExtractor(store=store, use_llm=False)
    rules = extractor.extract_from_source(source_doc)
    review = RuleReviewService(store=store)
    for r in rules:
        review.review(r.id, action="approve", reviewer="qa_bot")

    builder = RulePackBuilder(store=store)
    pack = builder.build(category="children_desk_mat")
    assert pack.status == "active"
    assert pack.metrics.approved_rule_count == len(rules)
    assert pack.default_strategy_archetypes, "儿童桌垫应有内置 archetype"

    # 同 category 再 build 一版应递增 version 且只有最新版 active
    pack2 = builder.build(category="children_desk_mat")
    assert pack2.version != pack.version
    refreshed_first = store.get_rule_pack(pack.id)
    assert refreshed_first is not None
    assert refreshed_first["status"] != "active"
    assert pack2.status == "active"


# ── context_compiler ─────────────────────────────────────────────

def test_context_compiler_manual(store: RuleStore) -> None:
    compiler = ContextCompiler(store=store)
    ctx = compiler.compile_manual(
        category="children_desk_mat",
        scene="taobao_main_image",
        product={"name": "护眼桌垫 60×40", "category": "children_desk_mat", "claims": ["防水", "耐磨"]},
        store_visual={"style": "暖色温馨", "colors": ["奶油白", "原木色"]},
        audience={"buyer": "宝妈", "user": "幼儿园儿童"},
        brand_profile={"workspace_id": "ws_01", "brand_id": "brd_01"},
    )
    assert ctx.category == "children_desk_mat"
    assert ctx.product.claims == ["防水", "耐磨"]
    assert "奶油白" in ctx.store_visual_system.colors
    assert ctx.audience.buyer == "宝妈"
    assert ctx.workspace_id == "ws_01"
    # 验证持久化
    persisted = store.get_context_spec(ctx.id)
    assert persisted is not None
    assert persisted["category"] == "children_desk_mat"
