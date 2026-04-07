#!/usr/bin/env python3
"""C1：最多 12 条 promoted 机会卡跑 build_note_plan，输出 Markdown 验收表。

用法（仓库根目录）：
  PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_acceptance_c1.py
  PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_acceptance_c1.py --with-generation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.content_planning.adapters.intel_hub_adapter import IntelHubAdapter
from apps.content_planning.exceptions import OpportunityNotPromotedError
from apps.content_planning.services.opportunity_to_plan_flow import OpportunityToPlanFlow


def main() -> int:
    parser = argparse.ArgumentParser(description="内容策划 C1：promoted 样本验收")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--with-generation", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    adapter = IntelHubAdapter()
    lim = max(1, args.limit)
    promoted = adapter.get_promoted_cards()[:lim]

    if not promoted:
        print("## C1 验收\n\n无 promoted 机会卡；请先在检视流程中升级。")
        return 0

    flow = OpportunityToPlanFlow(adapter=adapter)
    rows: list[dict[str, str]] = []
    failures: list[str] = []

    for card in promoted:
        oid = card.opportunity_id
        row = {
            "opportunity_id": oid,
            "brief_ok": "",
            "match_ok": "",
            "strategy_ok": "",
            "note_plan_ok": "",
            "titles_ok": "",
            "body_ok": "",
            "image_ok": "",
            "trace_ok": "",
            "pass": "",
        }
        try:
            result = flow.build_note_plan(oid, with_generation=args.with_generation)
        except (OpportunityNotPromotedError, ValueError) as e:
            failures.append(f"{oid}: {e}")
            row["pass"] = "否"
            rows.append(row)
            continue

        brief = result.get("brief") or {}
        np = result.get("note_plan") or {}
        row["brief_ok"] = "是" if brief.get("brief_id") and brief.get("opportunity_id") else "否"
        pt = (result.get("match_result") or {}).get("primary_template") or {}
        row["match_ok"] = "是" if pt.get("template_id") else "否"
        row["strategy_ok"] = "是" if (result.get("strategy") or {}).get("strategy_id") else "否"
        row["note_plan_ok"] = "是" if np.get("plan_id") and np.get("title_plan") and np.get("body_plan") else "否"
        img = np.get("image_plan") or {}
        row["trace_ok"] = "是" if (
            all(np.get(k) for k in ("opportunity_id", "brief_id", "strategy_id", "template_id"))
            and img.get("brief_id")
        ) else "否"

        if args.with_generation:
            gen = result.get("generated") or {}
            t, b, ib = gen.get("titles") or {}, gen.get("body") or {}, gen.get("image_briefs") or {}
            row["titles_ok"] = "是" if t.get("titles") else "否"
            row["body_ok"] = "是" if b.get("body_draft") else "否"
            row["image_ok"] = "是" if ib.get("slot_briefs") else "否"
        else:
            row["titles_ok"] = row["body_ok"] = row["image_ok"] = "—"

        ok = (
            row["brief_ok"] == "是"
            and row["match_ok"] == "是"
            and row["strategy_ok"] == "是"
            and row["note_plan_ok"] == "是"
            and row["trace_ok"] == "是"
        )
        if args.with_generation:
            ok = ok and row["titles_ok"] == "是" and row["body_ok"] == "是" and row["image_ok"] == "是"
        row["pass"] = "是" if ok else "否"
        rows.append(row)

    total = len(rows)
    passed = sum(1 for r in rows if r["pass"] == "是")
    pct = 100 * passed // total if total else 0
    print("## C1 内容策划链路验收\n")
    print(f"- 样本数: {total}（上限 {lim}）\n- 通过: {passed}/{total}（{pct}%）\n")

    hdr = ["opportunity_id", "brief", "match", "strategy", "note_plan", "titles", "body", "image", "trace", "通过"]
    print("| " + " | ".join(hdr) + " |")
    print("| " + " | ".join(["---"] * len(hdr)) + " |")
    for r in rows:
        print(
            "| "
            + " | ".join(
                [
                    r["opportunity_id"],
                    r["brief_ok"],
                    r["match_ok"],
                    r["strategy_ok"],
                    r["note_plan_ok"],
                    r["titles_ok"],
                    r["body_ok"],
                    r["image_ok"],
                    r["trace_ok"],
                    r["pass"],
                ]
            )
            + " |"
        )

    if failures:
        print("\n### 失败\n")
        for f in failures:
            print(f"- {f}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写 {args.json_out}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
