"""CategoryLensEngine —— 类目透视引擎主类。

职责：
1. 接收一组属于同一 Lens 的 `NoteContentFrame`（已可选带 BSF/VLM 结果）；
2. 对笔记组执行：词频统计 → 痛点/场景/信任抽取 → 商品映射 → 内容执行建议；
3. 产出 :class:`LensInsightBundle`（Category.md 第五节的五层模型）；
4. 计算机会卡五维打分（按 lens.scoring_weights 加权），并给出推荐动作。

输出可直接进入 compiler（Phase F）装配成 ``XHSOpportunityCard``。

设计原则：
- 纯函数式 + 无副作用，便于单元测试。
- 不依赖外部 LLM，所有打分基于规则 + TF-IDF + Lens 词库。
- 后续若接入 LLM 润色（如 hook/insight_summary），应作为可插拔 Hook，
  不影响五层结构本身。
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from apps.intel_hub.analysis.lens_keyword_stats import (
    compute_lens_hot_keywords,
    hits_to_dict_list,
)
from apps.intel_hub.domain.category_lens import (
    CategoryLens,
    ContentExecutionItem,
    EvidenceScore,
    Layer1Signals,
    LensInsightBundle,
    ProductMappingItem,
    RecommendedAction,
    UserJob,
)
from apps.intel_hub.extractor.signal_extractor import extract_business_signals
from apps.intel_hub.schemas.content_frame import BusinessSignalFrame, NoteContentFrame

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LensEngineInput:
    """传给 :class:`CategoryLensEngine` 的单篇笔记输入。"""

    frame: NoteContentFrame
    business_signals: BusinessSignalFrame | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class CategoryLensEngine:
    """以 ``CategoryLens`` 为视角汇总一组笔记并输出 ``LensInsightBundle``。"""

    def __init__(self, lens: CategoryLens) -> None:
        self.lens = lens

    # ── 主入口 ──────────────────────────────────────────

    def run(self, inputs: list[LensEngineInput]) -> LensInsightBundle:
        """按 Lens 视角处理一组笔记，返回五层机会卡模型。"""
        frames: list[NoteContentFrame] = []
        bsfs: list[BusinessSignalFrame] = []
        for item in inputs:
            frames.append(item.frame)
            bsf = item.business_signals or extract_business_signals(
                item.frame, lens=self.lens
            )
            bsfs.append(bsf)

        layer1 = self._build_layer1(frames, bsfs)
        ontology = self._build_layer2(bsfs)
        user_jobs = self._build_user_jobs(layer1, bsfs)
        mapping = self._build_product_mapping(layer1, bsfs)
        execution = self._build_content_execution(layer1, bsfs)
        score = self._build_score(layer1, bsfs, frames)
        action = self._build_action(score)

        return LensInsightBundle(
            lens_id=self.lens.lens_id,
            lens_version=self.lens.version,
            source_note_ids=[f.note_id for f in frames],
            layer1_signals=layer1,
            layer2_ontology=ontology,
            layer3_user_jobs=user_jobs,
            layer4_product_mapping=mapping,
            layer5_content_execution=execution,
            evidence_score=score,
            recommended_action=action,
        )

    # ── 第 1 层：内容信号 ───────────────────────────────

    def _build_layer1(
        self,
        frames: list[NoteContentFrame],
        bsfs: list[BusinessSignalFrame],
    ) -> Layer1Signals:
        hot_hits = compute_lens_hot_keywords(frames, self.lens, top_k=12)
        hot_keywords = hits_to_dict_list(hot_hits)

        note_patterns = self._top_items(
            _flatten([b.body_content_pattern_signals for b in bsfs]),
            limit=6,
        )
        comment_signals = self._top_items(
            _flatten([b.question_signals + b.trust_gap_signals for b in bsfs]),
            limit=8,
        )
        emotion_words = self._top_items(
            _flatten([b.body_emotion_signals + b.title_result_signals for b in bsfs]),
            limit=6,
        )
        scene_words = self._top_items(
            _flatten(
                [
                    b.body_scene_signals + b.title_scene_signals + b.visual_scene_signals
                    for b in bsfs
                ]
            ),
            limit=6,
        )
        trust_barrier_hits = self._top_items(
            _flatten(
                [
                    b.comment_trust_barrier_signals
                    + b.trust_gap_signals
                    + b.visual_trust_risk_flags
                    for b in bsfs
                ]
            ),
            limit=6,
        )

        visual_insight_summary = self._summarize_visual(bsfs)

        return Layer1Signals(
            hot_keywords=hot_keywords,
            note_patterns=note_patterns,
            comment_signals=comment_signals,
            emotion_words=emotion_words,
            scene_words=scene_words,
            trust_barrier_hits=trust_barrier_hits,
            visual_insight_summary=visual_insight_summary,
        )

    def _summarize_visual(self, bsfs: list[BusinessSignalFrame]) -> dict[str, Any]:
        style = self._top_items(_flatten([b.visual_style_signals for b in bsfs]), limit=5)
        scene = self._top_items(_flatten([b.visual_scene_signals for b in bsfs]), limit=5)
        composition = self._top_items(
            _flatten([b.visual_composition_types for b in bsfs]), limit=5
        )
        people_state = self._top_items(
            _flatten([b.visual_people_state for b in bsfs]), limit=5
        )
        trust_signals = self._top_items(
            _flatten([b.visual_trust_signals for b in bsfs]), limit=5
        )
        trust_risks = self._top_items(
            _flatten([b.visual_trust_risk_flags for b in bsfs]), limit=5
        )
        content_formats = self._top_items(
            _flatten([b.visual_content_formats for b in bsfs]), limit=5
        )
        product_features = self._top_items(
            _flatten([b.visual_product_features for b in bsfs]), limit=5
        )
        notes = [b.visual_insight_notes for b in bsfs if b.visual_insight_notes]

        return {
            "style": style,
            "scene": scene,
            "composition": composition,
            "people_state": people_state,
            "trust_signals": trust_signals,
            "trust_risks": trust_risks,
            "content_formats": content_formats,
            "product_features": product_features,
            "notes": notes[:6],
        }

    # ── 第 2 层：类目本体 ───────────────────────────────

    def _build_layer2(self, bsfs: list[BusinessSignalFrame]) -> dict[str, Any]:
        """以 Lens 的本体分类做收敛统计（仅表达"本体命中情况"）。"""
        return {
            "scene_refs": self._top_items(
                _flatten(
                    [
                        b.normalized_scene_refs
                        + b.body_scene_signals
                        + b.visual_scene_signals
                        for b in bsfs
                    ]
                ),
                limit=6,
            ),
            "style_refs": self._top_items(
                _flatten(
                    [
                        b.normalized_style_refs
                        + b.body_style_signals
                        + b.visual_style_signals
                        for b in bsfs
                    ]
                ),
                limit=6,
            ),
            "need_refs": self._top_items(
                _flatten(
                    [b.body_selling_points + b.visual_product_features for b in bsfs]
                ),
                limit=6,
            ),
            "risk_refs": self._top_items(
                _flatten([b.body_risk_signals + b.visual_trust_risk_flags for b in bsfs]),
                limit=6,
            ),
            "audience_refs": self._top_items(
                _flatten(
                    [
                        b.body_audience_signals
                        + b.audience_signals_from_comments
                        for b in bsfs
                    ]
                ),
                limit=6,
            ),
            "product_feature_refs": self._top_items(
                _flatten(
                    [b.body_material_signals + b.visual_product_features for b in bsfs]
                ),
                limit=6,
            ),
        }

    # ── 第 3 层：用户任务 ───────────────────────────────

    def _build_user_jobs(
        self,
        layer1: Layer1Signals,
        bsfs: list[BusinessSignalFrame],
    ) -> list[UserJob]:
        if not bsfs:
            return []

        audiences = self._top_items(
            _flatten(
                [b.body_audience_signals + b.audience_signals_from_comments for b in bsfs]
            ),
            limit=2,
        ) or self.lens.audience_personas[:1]
        scenes = layer1.scene_words or self.lens.scene_tasks[:1]
        pain_candidates = self._top_items(
            _flatten([b.body_pain_points + b.title_problem_signals for b in bsfs]),
            limit=2,
        ) or self.lens.key_pain_dimensions[:1]
        desired = self._top_items(
            _flatten([b.body_selling_points + b.visual_product_features for b in bsfs]),
            limit=2,
        ) or self.lens.product_feature_taxonomy[:1]

        jobs: list[UserJob] = []
        max_jobs = max(1, min(3, len(audiences)))
        for idx in range(max_jobs):
            jobs.append(
                UserJob(
                    who=audiences[idx] if idx < len(audiences) else audiences[0],
                    when=scenes[idx] if idx < len(scenes) else (scenes[0] if scenes else ""),
                    problem=pain_candidates[idx]
                    if idx < len(pain_candidates)
                    else (pain_candidates[0] if pain_candidates else ""),
                    desired_outcome="、".join(desired) if desired else "",
                    current_alternative="、".join(self.lens.content_patterns[:2]),
                    frustration="、".join(layer1.trust_barrier_hits[:2]),
                )
            )
        return jobs

    # ── 第 4 层：商品映射 ───────────────────────────────

    def _build_product_mapping(
        self,
        layer1: Layer1Signals,
        bsfs: list[BusinessSignalFrame],
    ) -> list[ProductMappingItem]:
        items: list[ProductMappingItem] = []

        user_phrase_hits = self._top_items(
            _flatten([b.body_user_expression_hits for b in bsfs]), limit=3
        )

        for mapping in self.lens.user_expression_map:
            if user_phrase_hits and mapping.user_phrase not in user_phrase_hits:
                continue
            items.append(
                ProductMappingItem(
                    user_need=mapping.user_phrase,
                    product_features=list(mapping.product_features),
                    sku_actions=[
                        f"上架支持 {feat} 的 SKU" for feat in mapping.product_features[:3]
                    ],
                    detail_page_actions=mapping.proof_shots,
                )
            )

        # 当用户话术未命中，用高频商品特征兜底生成一条通用映射，避免 compiler 空装。
        if not items:
            top_features = self._top_items(
                _flatten(
                    [b.body_material_signals + b.visual_product_features for b in bsfs]
                )
                or self.lens.product_feature_taxonomy,
                limit=3,
            )
            if top_features:
                items.append(
                    ProductMappingItem(
                        user_need=self.lens.core_consumption_logic or "消费者主诉",
                        product_features=top_features,
                        sku_actions=[f"上架/优化 {f} 版型" for f in top_features],
                        detail_page_actions=self.lens.visual_prompt_hints.trust_signal_taxonomy[:3],
                    )
                )
        return items

    # ── 第 5 层：内容执行 ───────────────────────────────

    def _build_content_execution(
        self,
        layer1: Layer1Signals,
        bsfs: list[BusinessSignalFrame],
    ) -> list[ContentExecutionItem]:
        note_patterns = layer1.note_patterns or self.lens.content_patterns[:2]
        hooks: list[str] = []
        for w in layer1.emotion_words[:3]:
            hooks.append(f"{w}，你可能不知道…")
        for w in layer1.trust_barrier_hits[:2]:
            hooks.append(f"关于「{w}」的真实测评")
        if not hooks:
            hooks = [f"一张图讲清楚{self.lens.category_cn}的真实体验"]

        script_structure = [
            "痛点场景开场（真人实拍）",
            "产品特征近距离证明",
            "信任点对比演示",
            "对比结果 / 使用后状态",
            "号召一句话（链接 or 同款）",
        ]
        required_assets = list(
            dict.fromkeys(
                self.lens.visual_prompt_hints.trust_signal_taxonomy[:4]
                + self.lens.visual_prompt_hints.focus[:2]
            )
        )
        if not required_assets:
            required_assets = [
                "前后对比",
                "近距离特写",
                "真实使用场景",
            ]

        metrics = [
            "完播率 / 平均播放时长",
            "收藏 / 加购率",
            "评论顾虑词频次",
            "点击链接率",
        ]

        items: list[ContentExecutionItem] = []
        for pattern in note_patterns[:3] or ["种草"]:
            items.append(
                ContentExecutionItem(
                    content_angle=f"{self.lens.category_cn} · {pattern}",
                    hooks=list(hooks),
                    script_structure=list(script_structure),
                    required_assets=list(required_assets),
                    metrics=list(metrics),
                )
            )
        return items

    # ── 机会评分 + 推荐动作 ───────────────────────────

    def _build_score(
        self,
        layer1: Layer1Signals,
        bsfs: list[BusinessSignalFrame],
        frames: list[NoteContentFrame],
    ) -> EvidenceScore:
        pain_hits = len(_flatten([b.body_pain_points + b.title_problem_signals for b in bsfs]))
        trust_gap_hits = len(
            _flatten(
                [
                    b.comment_trust_barrier_signals
                    + b.trust_gap_signals
                    + b.visual_trust_risk_flags
                    for b in bsfs
                ]
            )
        )
        product_fit_hits = len(
            _flatten(
                [
                    b.body_material_signals
                    + b.visual_product_features
                    + b.body_user_expression_hits
                    for b in bsfs
                ]
            )
        )
        execution_hits = len(
            _flatten([b.body_content_pattern_signals + b.visual_content_formats for b in bsfs])
        )
        scene_hits = len(layer1.scene_words)
        style_hits = len(layer1.visual_insight_summary.get("style", []))
        engagement = sum(
            (f.like_count + f.comment_count + f.collect_count + f.share_count) for f in frames
        )

        # 归一化到 [0, 10]
        def _scale(value: float, soft_cap: float) -> float:
            if soft_cap <= 0:
                return 0.0
            return round(min(10.0, (value / soft_cap) * 10.0), 2)

        note_count = max(1, len(frames))
        heat = _scale(engagement, soft_cap=max(500.0, 200.0 * note_count))
        pain = _scale(pain_hits, soft_cap=3.0 * note_count)
        trust_gap = _scale(trust_gap_hits, soft_cap=3.0 * note_count)
        product_fit = _scale(product_fit_hits, soft_cap=3.0 * note_count)
        execution = _scale(execution_hits, soft_cap=2.0 * note_count)
        scene = _scale(scene_hits, soft_cap=3.0)
        style = _scale(style_hits, soft_cap=3.0)
        competition_gap = 5.0  # 占位：需求-供给差距暂用中性值，后续可接市场信号

        weights = self.lens.scoring_weights.model_dump()
        # 兼容 scene_heat_score / style_trend_score 两个可选权重
        values = {
            "heat_score": heat,
            "pain_score": pain,
            "trust_gap_score": trust_gap,
            "product_fit_score": product_fit,
            "execution_score": execution,
            "competition_gap_score": competition_gap,
            "scene_heat_score": scene,
            "style_trend_score": style,
        }
        weight_sum = sum(max(0.0, float(w)) for w in weights.values()) or 1.0
        total = 0.0
        for key, w in weights.items():
            total += values[key] * (max(0.0, float(w)) / weight_sum)
        total = round(total, 2)

        return EvidenceScore(
            heat=heat,
            pain=pain,
            trust_gap=trust_gap,
            product_fit=product_fit,
            execution=execution,
            competition_gap=competition_gap,
            total=total,
        )

    def _build_action(self, score: EvidenceScore) -> RecommendedAction:
        if score.total >= 7.0:
            decision = "进入测试"
            steps = [
                "生成 3 套内容脚本",
                "选 3 款 SKU 做真人测评",
                f"{self.lens.category_cn} 投放 10 篇素人笔记",
                "回收评论中的顾虑词",
            ]
        elif score.total >= 5.0:
            decision = "补充证据"
            steps = [
                "补充更多同类目笔记样本",
                "补拍信任证据镜头（近距离、真实光）",
                "评论中挖掘未满足需求",
            ]
        else:
            decision = "暂缓"
            steps = [
                "样本不足或证据薄弱，先暂缓",
                "补充另一批关键词采集",
                "观察类目其他爆款模式",
            ]
        return RecommendedAction(decision=decision, next_steps=steps)

    # ── 工具 ─────────────────────────────────────────

    @staticmethod
    def _top_items(values: list[str], *, limit: int) -> list[str]:
        counter = Counter(v for v in values if v)
        return [val for val, _ in counter.most_common(limit)]


def _flatten(list_of_lists: list[list[str]]) -> list[str]:
    flat: list[str] = []
    for lst in list_of_lists or []:
        for v in lst or []:
            if v:
                flat.append(v)
    return flat


__all__ = [
    "CategoryLensEngine",
    "LensEngineInput",
]
