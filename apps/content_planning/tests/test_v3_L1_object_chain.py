"""L1：对象链、血缘追溯、版本与 ImageExecutionBrief 强类型。"""

from __future__ import annotations

from apps.content_planning.schemas.action_spec import ActionSpec, ActionSpecBundle
from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    ImageSlotBrief,
    TitleCandidate,
    TitleGenerationResult,
)
from apps.content_planning.schemas.export_package import ExportPackage
from apps.content_planning.schemas.image_execution_brief import ImageExecutionBrief
from apps.content_planning.schemas.lineage import PlanLineage
from apps.content_planning.schemas.note_plan import NewNotePlan
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import TemplateMatchResult
from apps.content_planning.schemas.variant import Variant, VariantSet


def test_all_listed_schema_objects_instantiate_with_defaults():
    assert PlanLineage()
    assert AssetBundle()
    assert Variant()
    assert VariantSet()
    assert ExportPackage()
    assert ImageExecutionBrief()
    assert TitleCandidate()
    assert TitleGenerationResult()
    assert BodyGenerationResult()
    assert ImageSlotBrief()
    assert ImageBriefGenerationResult()
    assert ActionSpec()
    assert ActionSpecBundle()


def test_full_chain_export_lineage_traces_to_opportunity():
    opportunity_id = "opp-chain-001"
    brief = OpportunityBrief(opportunity_id=opportunity_id, version=1)
    template = TemplateMatchResult(opportunity_id=opportunity_id, brief_id=brief.brief_id)
    strategy = RewriteStrategy(
        opportunity_id=opportunity_id,
        brief_id=brief.brief_id,
        template_id=template.primary_template.template_id or "tpl-1",
    )
    plan = NewNotePlan(
        opportunity_id=opportunity_id,
        brief_id=brief.brief_id,
        strategy_id=strategy.strategy_id,
        template_id=strategy.template_id,
    )
    lineage = PlanLineage(
        opportunity_id=opportunity_id,
        brief_id=brief.brief_id,
        template_id=strategy.template_id,
        strategy_id=strategy.strategy_id,
        plan_id=plan.plan_id,
    )
    bundle = AssetBundle(
        opportunity_id=opportunity_id,
        brief_id=brief.brief_id,
        strategy_id=strategy.strategy_id,
        plan_id=plan.plan_id,
        template_id=strategy.template_id,
        lineage=lineage,
    )
    export = ExportPackage(
        opportunity_id=opportunity_id,
        asset_bundle_id=bundle.asset_bundle_id,
        brief_id=brief.brief_id,
        strategy_id=strategy.strategy_id,
        plan_id=plan.plan_id,
        template_id=strategy.template_id,
        lineage=lineage,
    )
    assert export.lineage is not None
    assert export.lineage.opportunity_id == opportunity_id
    assert export.brief_id == brief.brief_id
    assert export.lineage.brief_id == brief.brief_id
    assert export.lineage.plan_id == plan.plan_id


def test_variant_set_has_brief_strategy_plan_fields():
    vs = VariantSet()
    assert hasattr(vs, "brief_id")
    assert hasattr(vs, "strategy_id")
    assert hasattr(vs, "plan_id")
    vs2 = VariantSet(brief_id="b1", strategy_id="s1", plan_id="p1")
    assert vs2.brief_id == "b1"
    assert vs2.strategy_id == "s1"
    assert vs2.plan_id == "p1"


def test_asset_bundle_top_level_brief_and_strategy():
    b = AssetBundle()
    assert hasattr(b, "brief_id")
    assert hasattr(b, "strategy_id")
    b2 = AssetBundle(brief_id="br-2", strategy_id="st-2")
    assert b2.brief_id == "br-2"
    assert b2.strategy_id == "st-2"


def test_multiple_versions_same_opportunity():
    opportunity_id = "opp-ver"
    brief_v1 = OpportunityBrief(opportunity_id=opportunity_id, version=1)
    brief_v2 = OpportunityBrief(opportunity_id=opportunity_id, version=2)
    assert brief_v1.version != brief_v2.version

    strat_v1 = RewriteStrategy(
        opportunity_id=opportunity_id, brief_id=brief_v1.brief_id, strategy_version=1
    )
    strat_v2 = RewriteStrategy(
        opportunity_id=opportunity_id, brief_id=brief_v2.brief_id, strategy_version=2
    )
    assert strat_v1.strategy_version != strat_v2.strategy_version

    plan_v1 = NewNotePlan(opportunity_id=opportunity_id, brief_id=brief_v1.brief_id, version=1)
    plan_v2 = NewNotePlan(opportunity_id=opportunity_id, brief_id=brief_v2.brief_id, version=2)
    assert plan_v1.version != plan_v2.version


def test_plan_lineage_parent_and_derived_fields():
    parent = PlanLineage(opportunity_id="o1", brief_id="b0")
    child = PlanLineage(
        opportunity_id="o1",
        brief_id="b1",
        parent_version_id="ver-parent",
        derived_from_id=parent.brief_id or "src-1",
    )
    assert child.parent_version_id == "ver-parent"
    assert child.derived_from_id


def test_image_execution_brief_typed_fields_and_asset_bundle_list():
    ib = ImageExecutionBrief(
        brief_id="img-br-1",
        slot_index=2,
        opportunity_id="opp-i",
        plan_id="pl-i",
        strategy_id="st-i",
        role="hero",
        intent="show product",
        subject="bottle",
        composition="center",
        visual_brief="soft light",
        copy_hints="minimal",
        status="draft",
    )
    expected_fields = (
        "brief_id",
        "slot_index",
        "opportunity_id",
        "plan_id",
        "strategy_id",
        "role",
        "intent",
        "subject",
        "composition",
        "visual_brief",
        "copy_hints",
        "status",
    )
    for name in expected_fields:
        assert hasattr(ib, name)
    bundle = AssetBundle(image_execution_briefs=[ib])
    assert len(bundle.image_execution_briefs) == 1
    assert isinstance(bundle.image_execution_briefs[0], ImageExecutionBrief)
