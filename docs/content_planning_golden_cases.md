# 内容策划链路 Golden Cases（C2）

JSON 产物：`data/exports/content_planning/golden_{opportunity_id}.json`（`*.json` 已 `.gitignore`）。

## 如何重新导出

```bash
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/export_golden_cases.py
```

## 合成参考（单元测试 mock）

见 `apps/content_planning/tests/test_e2e_flow.py`（`opportunity_status="promoted"`）。

---

## 当前状态

当前数据库中无 promoted 机会卡，无法导出 golden。请先完成检视升级。
