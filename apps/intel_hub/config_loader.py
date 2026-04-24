from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from apps.intel_hub.schemas.watchlist import Watchlist


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"


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


def clear_config_caches() -> None:
    load_runtime_settings.cache_clear()
    load_watchlists.cache_clear()
    load_ontology_mapping.cache_clear()
    load_scoring_config.cache_clear()
    load_dedupe_config.cache_clear()
