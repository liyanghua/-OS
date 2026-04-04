"""模板检索器：加载与查询模板库。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from apps.template_extraction.schemas.template import TableclothMainImageStrategyTemplate

logger = logging.getLogger(__name__)

_DEFAULT_TPL_DIR = Path(__file__).resolve().parents[3] / "data" / "template_extraction" / "templates"


class TemplateRetriever:
    """模板库检索。"""

    def __init__(self, templates_dir: str | Path | None = None):
        self._dir = Path(templates_dir) if templates_dir else _DEFAULT_TPL_DIR
        self._templates: dict[str, TableclothMainImageStrategyTemplate] = {}
        self._load()

    def _load(self) -> None:
        index_file = self._dir / "index.json"
        if not index_file.exists():
            logger.warning("模板索引不存在: %s", index_file)
            return
        index = json.loads(index_file.read_text(encoding="utf-8"))
        for entry in index:
            tpl_file = self._dir / f"{entry['template_id']}.json"
            if tpl_file.exists():
                data = json.loads(tpl_file.read_text(encoding="utf-8"))
                tpl = TableclothMainImageStrategyTemplate.model_validate(data)
                self._templates[tpl.template_id] = tpl
        logger.info("加载 %d 套模板", len(self._templates))

    def list_templates(self) -> list[TableclothMainImageStrategyTemplate]:
        return list(self._templates.values())

    def get_template(self, template_id: str) -> TableclothMainImageStrategyTemplate | None:
        return self._templates.get(template_id)

    def get_template_ids(self) -> list[str]:
        return list(self._templates.keys())
