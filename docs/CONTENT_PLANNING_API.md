# 内容策划工作台 API 说明（v2）

内容策划编译链由 `apps/content_planning` 提供，挂载在情报 Hub 的 FastAPI 应用上。

## 一、API 路由总览

### 编排型 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/content-planning/xhs-opportunities/{id}/generate-brief` | 生成 OpportunityBrief |
| POST | `/content-planning/xhs-opportunities/{id}/generate-note-plan` | 完整编排（brief → 选模板 → 策略 → plan） |
| POST | `/content-planning/xhs-opportunities/{id}/compile-note-plan` | 一键全链路（默认 mode=full） |

### 原子 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/content-planning/xhs-opportunities/{id}/match-templates` | Brief → 模板匹配 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-strategy` | 模板 → RewriteStrategy |
| POST | `/content-planning/xhs-opportunities/{id}/generate-titles` | 局部重生成标题 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-body` | 局部重生成正文 |
| POST | `/content-planning/xhs-opportunities/{id}/generate-image-briefs` | 局部重生成图片指令 |

### Brief 编辑

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/content-planning/briefs/{opportunity_id}` | 人工编辑 Brief |

### 会话查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/content-planning/session/{opportunity_id}` | 获取当前会话缓存 |

### 兼容路由（无前缀）

| POST | `/xhs-opportunities/{id}/generate-brief` | 同上 |
| POST | `/xhs-opportunities/{id}/generate-note-plan` | 同上 |

### 工作台页面路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/content-planning/brief/{opportunity_id}` | Brief 确认页 |
| GET | `/content-planning/strategy/{opportunity_id}` | 模板与策略页 |
| GET | `/content-planning/plan/{opportunity_id}` | 内容策划页 |

## 二、准入条件

- 仅当机会卡状态为 **`promoted`（已升级）** 时，可成功调用后半链路 API；否则返回 **403**。

## 三、请求体说明

### generate-note-plan / compile-note-plan

```json
{
  "with_generation": false,
  "preferred_template_id": null,
  "mode": "plan_only"
}
```

- `mode`: `"plan_only"` 仅返回 brief / 匹配 / 策略 / note_plan；`"full"` 额外生成标题/正文/图片指令。
- `preferred_template_id`: 指定模板 ID，不指定则用 top1。

### generate-strategy

```json
{
  "template_id": "tpl_001_scene_seed"
}
```

### PUT briefs/{opportunity_id}

```json
{
  "target_user": ["家居爱好者"],
  "target_scene": ["早餐桌"],
  "content_goal": "种草收藏",
  "primary_value": "仪式感",
  "visual_style_direction": ["温馨", "ins风"],
  "avoid_directions": ["促销感"],
  "template_hints": ["scene_seed"]
}
```

仅传需要修改的字段，未传的字段保持不变。编辑后下游缓存（策略/方案）自动失效。

## 四、错误码

| HTTP | 含义 |
|------|------|
| 404 | 机会卡不存在、模板库为空等 |
| 403 | 机会卡未 promoted |

## 五、工作台使用流程

```
机会池（/xhs-opportunities?status=promoted）
  ↓ 点击 "生成 Brief"
Brief 确认页（/content-planning/brief/{id}）
  ↓ 查看/编辑 Brief → 点击 "下一步"
模板与策略页（/content-planning/strategy/{id}）
  ↓ 选模板 → 查看策略 → 点击 "下一步"
内容策划页（/content-planning/plan/{id}）
  ↓ 查看三维策划 → 生成/重生成标题·正文·图片 → 导出
```

支持局部重生成：Brief 编辑后不需要整链重跑，可独立重生成策略、标题、正文或图片指令。

## 六、验收脚本

```bash
# 端到端验收（自动选取 promoted 卡，走完整链路）
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_e2e_acceptance.py

# 指定机会卡 ID
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_e2e_acceptance.py <opportunity_id>

# C1 批量验收
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/run_acceptance_c1.py

# C2 golden case 导出
PYTHONPATH=. .venv/bin/python apps/content_planning/scripts/export_golden_cases.py
```

## 七、curl 示例

```bash
# Brief
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/generate-brief" \
  -H "Content-Type: application/json" -H "Accept: application/json"

# 一键全链路
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/compile-note-plan" \
  -H "Content-Type: application/json" -d '{"mode":"full"}'

# 模板匹配
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/match-templates"

# 生成策略（指定模板）
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/generate-strategy" \
  -H "Content-Type: application/json" -d '{"template_id":"tpl_002_style_anchor"}'

# 局部重生成标题
curl -s -X POST "http://127.0.0.1:8000/content-planning/xhs-opportunities/{ID}/generate-titles"

# 编辑 Brief
curl -s -X PUT "http://127.0.0.1:8000/content-planning/briefs/{ID}" \
  -H "Content-Type: application/json" -d '{"target_scene":["下午茶","聚会"]}'
```
