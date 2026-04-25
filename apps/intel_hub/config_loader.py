from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from apps.intel_hub.domain.category_lens import CategoryLens
from apps.intel_hub.schemas.watchlist import Watchlist


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_CATEGORY_LENSES_DIR = DEFAULT_CONFIG_DIR / "category_lenses"


class RuntimeSettings(BaseModel):
    trendradar_output_dir: str
    storage_path: str
    b2b_platform_db_path: str = "data/b2b_platform.sqlite"
    job_queue_path: str | None = None
    crawl_status_path: str | None = None
    alerts_path: str | None = None
    embedded_crawl_worker_enabled: bool = True
    default_page_size: int = 20
    fixture_fallback_dir: str | None = None
    raw_snapshot_dir: str = "data/raw"
    include_rss: bool = True
    mediacrawler_sources: list[dict[str, Any]] = Field(default_factory=list)
    xhs_sources: list[dict[str, Any]] = Field(default_factory=list)
    xhs_aggregation: dict[str, Any] = Field(default_factory=dict)

    def resolved_output_dir(self) -> Path:
        return resolve_repo_path(self.trendradar_output_dir)

    def resolved_storage_path(self) -> Path:
        return resolve_repo_path(self.storage_path)

    def resolved_runtime_data_dir(self) -> Path:
        return self.resolved_storage_path().parent

    def resolved_job_queue_path(self) -> Path:
        if self.job_queue_path:
            return resolve_repo_path(self.job_queue_path)
        return self.resolved_runtime_data_dir() / "job_queue.json"

    def resolved_crawl_status_path(self) -> Path:
        if self.crawl_status_path:
            return resolve_repo_path(self.crawl_status_path)
        return self.resolved_runtime_data_dir() / "crawl_status.json"

    def resolved_alerts_path(self) -> Path:
        if self.alerts_path:
            return resolve_repo_path(self.alerts_path)
        return self.resolved_runtime_data_dir() / "alerts.json"

    def resolved_fixture_fallback_dir(self) -> Path | None:
        if not self.fixture_fallback_dir:
            return None
        return resolve_repo_path(self.fixture_fallback_dir)

    def resolved_raw_snapshot_dir(self) -> Path:
        return resolve_repo_path(self.raw_snapshot_dir)


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved_path = resolve_repo_path(path)
    data = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    return data or {}


@lru_cache(maxsize=8)
def load_runtime_settings(path: str | Path | None = None) -> RuntimeSettings:
    config_path = path or (DEFAULT_CONFIG_DIR / "runtime.yaml")
    return RuntimeSettings.model_validate(load_yaml(config_path))


@lru_cache(maxsize=4)
def load_watchlists(path: str | Path | None = None) -> list[Watchlist]:
    config_path = path or (DEFAULT_CONFIG_DIR / "watchlists.yaml")
    payload = load_yaml(config_path)
    return [Watchlist.model_validate(item) for item in payload.get("watchlists", [])]


@lru_cache(maxsize=4)
def load_ontology_mapping(path: str | Path | None = None) -> dict[str, Any]:
    config_path = path or (DEFAULT_CONFIG_DIR / "ontology_mapping.yaml")
    return load_yaml(config_path)


@lru_cache(maxsize=4)
def load_scoring_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = path or (DEFAULT_CONFIG_DIR / "scoring.yaml")
    return load_yaml(config_path)


@lru_cache(maxsize=4)
def load_dedupe_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = path or (DEFAULT_CONFIG_DIR / "dedupe.yaml")
    return load_yaml(config_path)


@lru_cache(maxsize=4)
def load_category_lenses(
    lenses_dir: str | Path | None = None,
) -> dict[str, CategoryLens]:
    """加载 ``config/category_lenses/*.yaml`` 下所有类目透镜。

    目录中以下划线开头的文件（如 ``_keyword_routing.yaml``）会被跳过，
    它们是辅助配置而非 lens 定义本身。
    """
    base_dir = Path(lenses_dir) if lenses_dir else DEFAULT_CATEGORY_LENSES_DIR
    if not base_dir.is_absolute():
        base_dir = resolve_repo_path(base_dir)
    if not base_dir.exists():
        return {}

    lenses: dict[str, CategoryLens] = {}
    for yaml_path in sorted(base_dir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        data = load_yaml(yaml_path)
        if not data:
            continue
        lens = CategoryLens.model_validate(data)
        lenses[lens.lens_id] = lens
    return lenses


@lru_cache(maxsize=4)
def load_lens_keyword_routing(
    routing_path: str | Path | None = None,
) -> dict[str, Any]:
    """加载关键词 → lens_id 的路由规则（``_keyword_routing.yaml``）。"""
    config_path = routing_path or (
        DEFAULT_CATEGORY_LENSES_DIR / "_keyword_routing.yaml"
    )
    if not Path(config_path).is_absolute():
        config_path = resolve_repo_path(config_path)
    if not Path(config_path).exists():
        return {"default_lens_id": None, "rules": []}
    return load_yaml(config_path)


def route_keyword_to_lens_id(
    keyword: str | None,
    *,
    routing: dict[str, Any] | None = None,
) -> str | None:
    """按照 ``_keyword_routing.yaml`` 的规则为单个关键词决定 lens_id。

    在 ingestion 阶段调用：``keyword`` 通常来自 ``mediacrawler_sources[*].keywords``
    或 ``xhs_sources[*].keywords`` 单个关键词。未命中返回 ``default_lens_id``。
    """
    routing = routing if routing is not None else load_lens_keyword_routing()
    default_lens_id = routing.get("default_lens_id") or None
    if not keyword:
        return default_lens_id

    keyword_lower = str(keyword).lower()
    for rule in routing.get("rules", []):
        lens_id = rule.get("lens_id")
        for token in rule.get("match_any", []):
            if not token:
                continue
            if str(token).lower() in keyword_lower:
                return lens_id
    return default_lens_id


def clear_config_caches() -> None:
    load_runtime_settings.cache_clear()
    load_watchlists.cache_clear()
    load_ontology_mapping.cache_clear()
    load_scoring_config.cache_clear()
    load_dedupe_config.cache_clear()
    load_category_lenses.cache_clear()
    load_lens_keyword_routing.cache_clear()
