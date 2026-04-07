"""TitleGenerator / BodyGenerator / ImageBriefGenerator 单元测试（规则降级模式）。"""

from apps.content_planning.schemas.note_plan import (
    BodyPlan,
    NewNotePlan,
    TitlePlan,
)
from apps.content_planning.schemas.rewrite_strategy import RewriteStrategy
from apps.content_planning.services.body_generator import BodyGenerator
from apps.content_planning.services.image_brief_generator import ImageBriefGenerator
from apps.content_planning.services.title_generator import TitleGenerator
from apps.template_extraction.schemas.agent_plan import ImageSlotPlan, MainImagePlan


def _make_plan() -> NewNotePlan:
    return NewNotePlan(
        plan_id="plan_001",
        opportunity_id="opp_001",
        note_goal="种草收藏",
        target_user=["精致宝妈"],
        target_scene=["早餐", "居家"],
        core_selling_point="氛围感强",
        title_plan=TitlePlan(
            title_axes=["场景代入", "利益点"],
            candidate_titles=["[参考] 氛围感拉满的早餐桌布"],
            do_not_use_phrases=["全网最低"],
        ),
        body_plan=BodyPlan(
            opening_hook="最近入了一块桌布",
            body_outline=["核心卖点介绍", "场景搭配", "推荐总结"],
            cta_direction="收藏/关注",
        ),
        image_plan=MainImagePlan(
            plan_id="img_001",
            template_id="tpl_001",
            template_name="场景种草型",
            image_slots=[
                ImageSlotPlan(
                    slot_index=1,
                    role="hook_click",
                    intent="封面拉点击",
                    visual_brief="俯拍桌布全景",
                    must_include_elements=["桌布", "餐具"],
                    avoid_elements=["强促销"],
                ),
                ImageSlotPlan(
                    slot_index=2,
                    role="style_expand",
                    intent="风格延展",
                    visual_brief="风格细节",
                ),
            ],
        ),
    )


def _make_strategy() -> RewriteStrategy:
    return RewriteStrategy(
        strategy_id="st_001",
        positioning_statement="氛围感场景种草",
        new_hook="场景代入——聚焦氛围感",
        tone_of_voice="分享感、真实感",
        image_strategy=["图组: 吸睛→风格→质感"],
    )


def test_title_generator_rule_fallback():
    gen = TitleGenerator()
    result = gen._rule_fallback(_make_plan(), _make_strategy())
    assert result.mode == "rule"
    assert len(result.titles) >= 3
    assert all(t.title_text for t in result.titles)


def test_body_generator_rule_fallback():
    gen = BodyGenerator()
    result = gen._rule_fallback(_make_plan(), _make_strategy())
    assert result.mode == "rule"
    assert result.body_draft
    assert result.opening_hook
    assert result.cta_text


def test_image_brief_generator_rule_fallback():
    gen = ImageBriefGenerator()
    result = gen._rule_fallback(_make_plan(), _make_strategy())
    assert result.mode == "rule"
    assert len(result.slot_briefs) == 2
    assert result.slot_briefs[0].role == "hook_click"


def test_image_brief_no_plan():
    gen = ImageBriefGenerator()
    plan = _make_plan()
    plan.image_plan = None
    result = gen.generate(plan, _make_strategy())
    assert result.mode == "no_image_plan"
    assert len(result.slot_briefs) == 0
