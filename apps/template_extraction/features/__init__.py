"""模板抽取：特征工程入口。"""

from __future__ import annotations

from apps.template_extraction.features.feature_pipeline import run_feature_pipeline
from apps.template_extraction.features.gallery_analyzer import analyze_gallery
from apps.template_extraction.features.image_features import (
    detect_elements_from_text,
    extract_image_features,
)
from apps.template_extraction.features.label_features import vectorize_labels
from apps.template_extraction.features.text_features import extract_text_features

__all__ = [
    "analyze_gallery",
    "detect_elements_from_text",
    "extract_image_features",
    "extract_text_features",
    "run_feature_pipeline",
    "vectorize_labels",
]
