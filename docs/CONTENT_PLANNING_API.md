# 内容策划 API 说明

内容策划编译链由 `apps/content_planning` 提供，挂载在情报 Hub 的 FastAPI 应用上。

## 路径（两种等价入口）

| 说明 | 方法 | 路径 |
|------|------|------|
| 推荐（带模块前缀） | POST | `/content-planning/xhs-opportunities/{opportunity_id}/generate-brief` |
| 推荐（带模块前缀） | POST | `/content-planning/xhs-opportunities/{opportunity_id}/generate-note-plan` |
| 兼容（验收文档 A3 无前缀） | POST | `/xhs-opportunities/{opportunity_id}/generate-brief` |
| 兼容（验收文档 A3 无前缀） | POST | `/xhs-opportunities/{opportunity_id}/generate-note-plan` |

实现位置：[apps/content_planning/api/routes.py](apps/content_planning/api/routes.py)。

## 准入条件

- 仅当机会卡在存储中状态为 **`promoted`（已升级）** 时，可成功生成 Brief 与策划；否则返回 **403**，详情见响应 `detail`。

## generate-note-plan 请求体

```json
{
  "with_generation": false,
  "preferred_template_id": null,
  "mode": "plan_only"
}
```

- `mode`: `"plan_only"`（默认）仅返回 brief / 匹配 / 策略 / `note_plan`；`"full"` 等价于开启内容生成（与 `with_generation: true` 叠加任一即可触发生成）。
- `with_generation`: 为 `true` 时额外返回 `generated.titles`、`generated.body`、`generated.image_briefs`。

## 错误码

| HTTP | 含义 |
|------|------|
| 404 | 机会卡不存在，或模板库为空等业务 `ValueError` |
| 403 | 机会卡存在但未 `promoted` |

## curl 示例

```bash
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/generate-brief" \
  -H "Content-Type: application/json" -H "Accept: application/json"

curl -s -X POST "http://127.0.0.1:8000/xhs-opportunities/{ID}/generate-note-plan" \
  -H "Content-Type: application/json" -d '{"mode":"full"}'
```

## 验收脚本

- C1（最多 12 条 promoted）：`PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_acceptance_c1.py`
- C2（最多 3 条 golden JSON）：`PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/export_golden_cases.py`
