"""VariantGenerator：从现有 AssetBundle 派生变体。"""

from __future__ import annotations

import logging

from apps.content_planning.schemas.asset_bundle import AssetBundle
from apps.content_planning.schemas.variant import Variant, VariantSet

logger = logging.getLogger(__name__)


class VariantGenerator:
    """基于轴维度从已有资产包派生变体。"""

    @staticmethod
    def generate_variant(
        bundle: AssetBundle,
        axis: str = "tone",
        label: str = "",
    ) -> Variant:
        snapshot = bundle.model_dump(mode="json")
        snapshot.pop("asset_bundle_id", None)
        snapshot.pop("variant_set_id", None)

        return Variant(
            parent_bundle_id=bundle.asset_bundle_id,
            variant_axis=axis,
            variant_label=label or f"{axis} 变体",
            asset_snapshot=snapshot,
        )

    @staticmethod
    def create_variant_set(
        bundle: AssetBundle,
        axes: list[str] | None = None,
    ) -> VariantSet:
        axes = axes or ["tone"]
        vs = VariantSet(
            opportunity_id=bundle.opportunity_id,
            parent_bundle_id=bundle.asset_bundle_id,
        )
        for axis in axes:
            v = VariantGenerator.generate_variant(bundle, axis)
            vs.variants.append(v)
        return vs
