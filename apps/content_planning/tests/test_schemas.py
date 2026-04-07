"""Schema 构造与序列化测试。"""

from apps.content_planning.schemas.content_generation import (
    BodyGenerationResult,
    ImageBriefGenerationResult,
    ImageSlotBrief,
    TitleCandidate,
    TitleGenerationResult,
)
from apps.content_planning.schemas.note_plan import (
    BodyPlan,
    NewNotePlan,
    TitlePlan,
)
from apps.content_planning.schemas.opportunity_brief import OpportunityBrief
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.schemas.template_match_result import (
    TemplateMatchEntry,
    TemplateMatchResult,
)


def test_opportunity_brief_defaults():
    brief = OpportunityBrief(opportunity_id="opp_001")
    assert brief.opportunity_id == "opp_001"
    assert brief.brief_id
    assert brief.target_user == []
    d = brief.model_dump(mode="json")
    assert d["opportunity_id"] == "opp_001"


def test_rewrite_strategy_roundtrip():
    s = RewriteStrategy(
        opportunity_id="opp_001",
        brief_id="br_001",
        template_id="tpl_001",
        positioning_statement="测试定位",
        title_strategy=["标题方向1", "标题方向2"],
    )
    d = s.model_dump(mode="json")
    s2 = RewriteStrategy.model_validate(d)
    assert s2.positioning_statement == "测试定位"
    assert len(s2.title_strategy) == 2


def test_note_plan_with_nested_plans():
    plan = NewNotePlan(
        opportunity_id="opp_001",
        title_plan=TitlePlan(title_axes=["场景", "利益点"]),
        body_plan=BodyPlan(opening_hook="开头钩子", body_outline=["段1", "段2"]),
    )
    d = plan.model_dump(mode="json")
    assert d["title_plan"]["title_axes"] == ["场景", "利益点"]
    assert d["body_plan"]["opening_hook"] == "开头钩子"


def test_title_generation_result():
    r = TitleGenerationResult(
        plan_id="p1",
        titles=[TitleCandidate(title_text="标题1", axis="场景", rationale="测试")],
        mode="rule",
    )
    assert len(r.titles) == 1
    assert r.titles[0].title_text == "标题1"


def test_body_generation_result():
    r = BodyGenerationResult(plan_id="p1", body_draft="正文", mode="rule")
    assert r.body_draft == "正文"


def test_image_brief_generation_result():
    r = ImageBriefGenerationResult(
        plan_id="p1",
        slot_briefs=[ImageSlotBrief(slot_index=1, role="cover_hook", subject="桌布")],
    )
    assert len(r.slot_briefs) == 1


def test_template_match_result():
    r = TemplateMatchResult(
        opportunity_id="opp_001",
        brief_id="br_001",
        primary_template=TemplateMatchEntry(template_id="tpl_001", template_name="场景种草", score=0.8),
        secondary_templates=[
            TemplateMatchEntry(template_id="tpl_002", template_name="风格定锚", score=0.5),
        ],
    )
    assert r.primary_template.score == 0.8
    assert len(r.secondary_templates) == 1
