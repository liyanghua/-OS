#!/usr/bin/env python3
"""C2：导出最多 3 条 promoted 机会卡的完整 generate-note-plan JSON，并更新 golden 说明文档。

用法（仓库根目录）：
  PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/export_golden_cases.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow

_EXPORT_DIR = _REPO_ROOT / "data" / "exports" / "content_planning"
_DOC_PATH = _REPO_ROOT / "docs" / "content_planning_golden_cases.md"

_DOC_INTRO = """# 内容策划链路 Golden Cases（C2）

JSON 产物：`data/exports/content_planning/golden_{opportunity_id}.json`（`*.json` 已 `.gitignore`）。

## 如何重新导出

```bash
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/export_golden_cases.py
```

## 合成参考（单元测试 mock）

见 `apps/content_planning/tests/test_e2e_flow.py`（`opportunity_status="promoted"`）。

---
"""


def main() -> int:
    adapter = IntelHubAdapter()
    promoted = adapter.get_promoted_cards()[:3]
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not promoted:
        _DOC_PATH.write_text(
            _DOC_INTRO
            + "\n## 当前状态\n\n当前数据库中无 promoted 机会卡，无法导出 golden。请先完成检视升级。\n",
            encoding="utf-8",
        )
        print(f"已写入占位说明: {_DOC_PATH}")
        return 0

    flow = OpportunityToPlanFlow(adapter=adapter)
    lines: list[str] = [
        _DOC_INTRO,
        f"## 导出批次\n\n- 时间（UTC）: {datetime.now(UTC).isoformat()}\n",
        "- 每条为 `build_note_plan(..., with_generation=True)` 完整 JSON。\n",
    ]

    for i, card in enumerate(promoted, start=1):
        oid = card.opportunity_id
        try:
            payload = flow.build_note_plan(oid, with_generation=True)
        except Exception as exc:
            lines.append(f"\n## Case {i}: {oid}\n\n**导出失败**: `{exc}`\n")
            continue

        out_file = _EXPORT_DIR / f"golden_{oid}.json"
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        brief = payload.get("brief") or {}
        titles = (payload.get("generated") or {}).get("titles") or {}
        n_titles = len(titles.get("titles") or [])
        lines.append(f"\n## Case {i}: `{oid}`\n")
        lines.append(f"- 机会标题: {brief.get('opportunity_title', '')[:80]}\n")
        lines.append(f"- JSON: [`{out_file.relative_to(_REPO_ROOT)}`]({out_file.relative_to(_REPO_ROOT)})\n")
        lines.append(f"- 标题候选数: {n_titles}\n")

    _DOC_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"已导出 {len(promoted)} 条 JSON 到 {_EXPORT_DIR}")
    print(f"索引文档: {_DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
