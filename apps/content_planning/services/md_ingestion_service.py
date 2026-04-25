"""md_ingestion_service — 扫描 assets/SOP/{category}/*.md 并入库。

约定：
- 文件名前缀编号映射六大维度：01=visual_core, 02=people_interaction,
  03=function_selling_point, 04=pattern_style, 05=marketing_info, 06=differentiation。
- 每个文件保存为一个 SourceDocument，原始 MD 全文保留以便审核台回链。
- 入库后由 rule_extractor.extract_from_source 进一步抽 RuleSpec 候选。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from apps.content_planning.schemas.source_document import SOPDimension, SourceDocument
from apps.content_planning.storage.rule_store import RuleStore

logger = logging.getLogger(__name__)

# 仓库根 / assets 根
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ASSETS_SOP_ROOT = _REPO_ROOT / "assets" / "SOP"


# 文件名前缀编号 -> 维度
_PREFIX_TO_DIMENSION: dict[str, SOPDimension] = {
    "01": "visual_core",
    "02": "people_interaction",
    "03": "function_selling_point",
    "04": "pattern_style",
    "05": "marketing_info",
    "06": "differentiation",
}

_PREFIX_RE = re.compile(r"(\d{2})\.md$")


def _resolve_dimension(file_name: str) -> SOPDimension:
    match = _PREFIX_RE.search(file_name)
    if not match:
        return "visual_core"
    return _PREFIX_TO_DIMENSION.get(match.group(1), "visual_core")


def _category_dir(category: str) -> Path:
    """允许 slug（children_desk_mat）也允许中文目录名（儿童桌垫）。"""
    candidate_slug = _ASSETS_SOP_ROOT / category
    if candidate_slug.is_dir():
        return candidate_slug
    # 落到 alias map（中文 → slug 反查）
    alias_map = _category_alias_map()
    if category in alias_map:
        slug = alias_map[category]
        candidate_alias = _ASSETS_SOP_ROOT / slug
        if candidate_alias.is_dir():
            return candidate_alias
    # 最后尝试反向：传入 slug 找中文目录
    for cn_name, slug in alias_map.items():
        if slug == category and (_ASSETS_SOP_ROOT / cn_name).is_dir():
            return _ASSETS_SOP_ROOT / cn_name
    return candidate_slug


def _category_alias_map() -> dict[str, str]:
    """中文目录 → slug 映射；当类目扩展时在此增加条目即可。"""
    return {
        "儿童桌垫": "children_desk_mat",
    }


def category_to_slug(category: str) -> str:
    alias = _category_alias_map()
    return alias.get(category, category)


class MDIngestionService:
    """SOP MD 入库服务。"""

    def __init__(self, store: RuleStore | None = None) -> None:
        self.store = store or RuleStore()

    def ingest_category(self, category: str) -> list[SourceDocument]:
        """扫描某类目下所有 *.md 入库，返回 SourceDocument 列表。"""
        directory = _category_dir(category)
        if not directory.is_dir():
            logger.warning("[md_ingest] 目录不存在: %s", directory)
            return []

        slug = category_to_slug(category)
        results: list[SourceDocument] = []

        md_files = sorted(directory.glob("*.md"))
        for path in md_files:
            doc = self._ingest_file(path, slug)
            results.append(doc)

        logger.info("[md_ingest] category=%s ingested=%d files", slug, len(results))
        return results

    def _ingest_file(self, path: Path, category_slug: str) -> SourceDocument:
        raw = path.read_text(encoding="utf-8")
        title = self._extract_title(raw) or path.stem
        dimension = _resolve_dimension(path.name)

        doc = SourceDocument(
            category=category_slug,
            title=title,
            file_name=path.name,
            file_path=str(path.relative_to(_REPO_ROOT)),
            dimension=dimension,
            raw_markdown=raw,
            status="parsed",
        )
        self.store.save_source_document(doc.model_dump())
        return doc

    @staticmethod
    def _extract_title(raw: str) -> str:
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""
