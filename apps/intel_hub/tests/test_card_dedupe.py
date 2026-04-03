import unittest


class CardDedupeTests(unittest.TestCase):
    def test_similar_opportunity_signals_merge_into_one_card(self) -> None:
        from apps.intel_hub.compiler.opportunity_compiler import compile_opportunity_cards
        from apps.intel_hub.schemas import Signal

        signals = [
            Signal(
                id="signal_1",
                title="Alpha launches AI intelligence hub",
                summary="Alpha launches AI intelligence hub for brands",
                entity_refs=["competitor:alpha"],
                canonical_entity_refs=["competitor:alpha"],
                topic_tags=["opportunity", "competitor"],
                timestamps={"published_at": "2026-04-03T10:00:00+00:00"},
                evidence_refs=["evidence_1"],
                business_priority_score=0.82,
            ),
            Signal(
                id="signal_2",
                title="Competitor Alpha launches AI intel hub",
                summary="Competitor Alpha launches AI intel hub",
                entity_refs=["competitor:alpha"],
                canonical_entity_refs=["competitor:alpha"],
                topic_tags=["opportunity", "competitor"],
                timestamps={"published_at": "2026-04-03T11:00:00+00:00"},
                evidence_refs=["evidence_2"],
                business_priority_score=0.8,
            ),
        ]
        ontology_mapping = {"card_compiler": {"opportunity_topics": ["opportunity", "competitor"]}}
        dedupe_config = {
            "merge_window_hours": 72,
            "minimum_evidence_count": 1,
            "title_token_overlap_threshold": 0.5,
            "max_cards_per_entity_topic_window": 3,
        }

        cards = compile_opportunity_cards(signals, ontology_mapping, dedupe_config)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].merged_signal_ids, ["signal_1", "signal_2"])
        self.assertEqual(cards[0].merged_evidence_refs, ["evidence_1", "evidence_2"])
        self.assertTrue(cards[0].dedupe_key)

    def test_non_similar_signals_do_not_merge(self) -> None:
        from apps.intel_hub.compiler.risk_compiler import compile_risk_cards
        from apps.intel_hub.schemas import Signal

        signals = [
            Signal(
                id="risk_1",
                title="Platform policy update on AI marketing disclosure",
                summary="Disclosure update",
                entity_refs=["policy:ai_marketing"],
                canonical_entity_refs=["policy:ai_marketing"],
                topic_tags=["risk", "platform_policy"],
                timestamps={"published_at": "2026-04-03T10:00:00+00:00"},
                evidence_refs=["evidence_a"],
                business_priority_score=0.9,
            ),
            Signal(
                id="risk_2",
                title="Platform policy expands account verification rules",
                summary="Verification rule update",
                entity_refs=["policy:ai_marketing"],
                canonical_entity_refs=["policy:ai_marketing"],
                topic_tags=["risk", "platform_policy"],
                timestamps={"published_at": "2026-04-03T12:00:00+00:00"},
                evidence_refs=["evidence_b"],
                business_priority_score=0.88,
            ),
        ]
        ontology_mapping = {"card_compiler": {"risk_topics": ["risk", "platform_policy"]}}
        dedupe_config = {
            "merge_window_hours": 72,
            "minimum_evidence_count": 1,
            "title_token_overlap_threshold": 0.9,
            "max_cards_per_entity_topic_window": 3,
        }

        cards = compile_risk_cards(signals, ontology_mapping, dedupe_config)

        self.assertEqual(len(cards), 2)


if __name__ == "__main__":
    unittest.main()
