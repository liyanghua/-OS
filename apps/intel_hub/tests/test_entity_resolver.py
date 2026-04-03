import unittest


class EntityResolverTests(unittest.TestCase):
    def test_aliases_map_to_single_canonical_entity(self) -> None:
        from apps.intel_hub.projector.entity_resolver import resolve_entities
        from apps.intel_hub.schemas import Signal
        from apps.intel_hub.schemas.watchlist import Watchlist

        signal = Signal(
            id="signal_alpha",
            title="  ALPHA   AI launches Ontology Brain  ",
            summary="Competitor Alpha expands into AI-native intelligence hub",
            raw_text="alpha ai and competitor alpha appear in the same post",
        )
        watchlists = [
            Watchlist(
                id="competitor_alpha",
                watchlist_type="competitor",
                title="Competitor Alpha",
                entity_refs=["competitor:alpha"],
                keywords=["competitor alpha"],
                aliases=["alpha ai", "alpha"],
            ),
            Watchlist(
                id="ai_native_intel_hub",
                watchlist_type="category",
                title="AI-native intelligence hub",
                entity_refs=["category:ai_native_intel_hub"],
                keywords=["ai-native intelligence hub"],
                aliases=["ontology brain"],
            ),
        ]
        ontology_mapping = {
            "entities": {
                "competitor:alpha": {
                    "entity_type": "competitor",
                    "aliases": ["competitor alpha", "alpha ai", "alpha"],
                    "watchlist_ids": ["competitor_alpha"],
                },
                "category:ai_native_intel_hub": {
                    "entity_type": "category",
                    "aliases": ["ai-native intelligence hub", "ontology brain"],
                    "watchlist_ids": ["ai_native_intel_hub"],
                },
            }
        }

        resolution = resolve_entities(signal, watchlists, ontology_mapping, max_entities_per_signal=3)

        self.assertEqual(resolution.canonical_entity_refs, ["category:ai_native_intel_hub", "competitor:alpha"])
        self.assertIn("alpha ai", resolution.raw_entity_hits)
        self.assertEqual(len([ref for ref in resolution.canonical_entity_refs if ref == "competitor:alpha"]), 1)

    def test_same_type_entity_hits_are_deduped(self) -> None:
        from apps.intel_hub.projector.entity_resolver import resolve_entities
        from apps.intel_hub.schemas import Signal
        from apps.intel_hub.schemas.watchlist import Watchlist

        signal = Signal(
            id="signal_policy",
            title="Platform Policy Center issues policy update",
            summary="Policy Update from platform policy center",
            raw_text="platform policy and policy update",
        )
        watchlists = [
            Watchlist(
                id="platform_policy_ai_marketing",
                watchlist_type="platform_policy",
                title="AI marketing policy",
                entity_refs=["policy:ai_marketing"],
                keywords=["platform policy"],
                aliases=["policy update", "platform policy center"],
            )
        ]
        ontology_mapping = {
            "entities": {
                "policy:ai_marketing": {
                    "entity_type": "platform_policy",
                    "aliases": ["platform policy", "policy update", "platform policy center"],
                    "watchlist_ids": ["platform_policy_ai_marketing"],
                }
            }
        }

        resolution = resolve_entities(signal, watchlists, ontology_mapping, max_entities_per_signal=2)

        self.assertEqual(resolution.canonical_entity_refs, ["policy:ai_marketing"])
        self.assertGreaterEqual(len(resolution.raw_entity_hits), 2)


if __name__ == "__main__":
    unittest.main()
