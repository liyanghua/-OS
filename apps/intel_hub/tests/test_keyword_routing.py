"""Regression tests for ``route_keyword_to_lens_id`` longest-token-first
matching, after splitting children_desk_mat out of the tablecloth lens."""
from __future__ import annotations

import unittest

from apps.intel_hub.config_loader import (
    clear_config_caches,
    load_lens_keyword_routing,
    route_keyword_to_lens_id,
)


class KeywordRoutingTests(unittest.TestCase):
    """Production yaml integration cases — verify real config loads correctly."""

    def setUp(self) -> None:
        clear_config_caches()

    def test_儿童桌垫_routes_to_children_desk_mat(self) -> None:
        self.assertEqual(route_keyword_to_lens_id("儿童桌垫"), "children_desk_mat")

    def test_儿童学习桌垫_routes_to_children_desk_mat(self) -> None:
        self.assertEqual(route_keyword_to_lens_id("儿童学习桌垫"), "children_desk_mat")

    def test_宝宝桌垫_routes_to_children_desk_mat(self) -> None:
        self.assertEqual(route_keyword_to_lens_id("宝宝桌垫"), "children_desk_mat")

    def test_桌垫_alone_still_routes_to_tablecloth(self) -> None:
        """纯 `桌垫` 仍归 tablecloth（兼容历史行为）。"""
        self.assertEqual(route_keyword_to_lens_id("桌垫"), "tablecloth")

    def test_餐桌布_routes_to_tablecloth(self) -> None:
        self.assertEqual(route_keyword_to_lens_id("餐桌布"), "tablecloth")

    def test_假发_routes_to_wig(self) -> None:
        """wig 规则不受 children_desk_mat 新增影响。"""
        self.assertEqual(route_keyword_to_lens_id("假发"), "wig")

    def test_default_lens_id_when_no_match(self) -> None:
        routing = load_lens_keyword_routing()
        default = routing.get("default_lens_id")
        self.assertEqual(route_keyword_to_lens_id("完全不相关的关键词"), default)
        self.assertEqual(route_keyword_to_lens_id(""), default)
        self.assertEqual(route_keyword_to_lens_id(None), default)


class LongestTokenWinsTests(unittest.TestCase):
    """Algorithmic cases — synthetic routing dict to assert longest-token-first
    independent of production yaml content."""

    def test_longer_token_beats_shorter_substring(self) -> None:
        routing = {
            "default_lens_id": "fallback",
            "rules": [
                {"lens_id": "tablecloth", "match_any": ["桌垫"]},
                {"lens_id": "children_desk_mat", "match_any": ["儿童桌垫"]},
            ],
        }
        self.assertEqual(
            route_keyword_to_lens_id("儿童桌垫", routing=routing),
            "children_desk_mat",
        )

    def test_tied_token_length_takes_first_rule(self) -> None:
        """两条规则的命中 token 同样长度时，按 yaml 中书写顺序取首条。"""
        routing = {
            "default_lens_id": "fallback",
            "rules": [
                {"lens_id": "lensA", "match_any": ["桌垫"]},
                {"lens_id": "lensB", "match_any": ["桌垫"]},
            ],
        }
        self.assertEqual(
            route_keyword_to_lens_id("桌垫", routing=routing),
            "lensA",
        )

    def test_short_token_only_keyword_falls_back_to_short_rule(self) -> None:
        """关键词中没有长 token 时，仍按短 token 命中。"""
        routing = {
            "default_lens_id": "fallback",
            "rules": [
                {"lens_id": "tablecloth", "match_any": ["桌垫"]},
                {"lens_id": "children_desk_mat", "match_any": ["儿童桌垫"]},
            ],
        }
        self.assertEqual(
            route_keyword_to_lens_id("桌垫", routing=routing),
            "tablecloth",
        )

    def test_unknown_keyword_returns_default(self) -> None:
        routing = {
            "default_lens_id": "fallback",
            "rules": [{"lens_id": "tablecloth", "match_any": ["桌垫"]}],
        }
        self.assertEqual(
            route_keyword_to_lens_id("毫不相关", routing=routing),
            "fallback",
        )


if __name__ == "__main__":
    unittest.main()
