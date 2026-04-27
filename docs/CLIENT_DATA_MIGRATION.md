# 客户侧数据迁移与首部署 Quickstart

本指南面向**客户侧服务器首部署**场景：让客户在不依赖浏览器采集、不重新跑 LLM
pipeline 的前提下，直接把本机已采的全套运行时数据搬到服务器，跑完 `install.sh`
即可点开页面看到机会卡、规划工作台、视觉策略包等真实内容。

设计上分两条链路：

| 模式      | 说明                                                | 适用场景                              |
| --------- | --------------------------------------------------- | ------------------------------------- |
| 快照模式  | 打包业务 SQLite / output / 资源目录，服务器解包即可 | 默认；客户现场无 LLM key、无登录态    |
| 重建模式  | 仅传 raw jsonl，服务器侧 LLM key 已配置后重新跑   | 客户希望从原始数据自治；接受 token 费 |

涉及的脚本：

| 路径                                        | 角色                                       |
| ------------------------------------------- | ------------------------------------------ |
| `scripts/export_dataset.sh`                 | 本机一键导出业务数据快照 + MediaCrawler jsonl |
| `scripts/bootstrap_data.sh`                 | 服务器侧解包、清理运行态、停/起 systemd     |
| `apps/intel_hub/scripts/bootstrap_data.py`  | Python 子 CLI：sync / validate / summary   |
| `install.sh --bundle <tar.gz>`              | 安装末尾自动调用 bootstrap_data.sh         |

---

## 一、本机：导出快照

```bash
# 全量（默认，含 raw / fixtures / MediaCrawler jsonl）
bash scripts/export_dataset.sh
# 产物落到 dist/dataset_<ts>.tar.gz

# 仅核心（sqlite + opportunity_cards JSON），体积最小
bash scripts/export_dataset.sh --lite

# 自定义输出路径
bash scripts/export_dataset.sh --out /tmp/dataset.tar.gz

# 默认会跳过 data/sessions（含 cookie），如需带上：
bash scripts/export_dataset.sh --include-sessions
```

导出脚本会做这些事：

1. 对每个 SQLite 文件调 `sqlite3 .backup`，避免运行中拷出不一致状态；
2. 把 `data/output/`、`data/raw/`、`data/raw_lake/`、`data/fixtures/`、
   `third_party/MediaCrawler/data/{xhs,douyin}/jsonl/` 一并打包；
3. 默认**不**打包 `data/job_queue.json`、`data/alerts.json`、`data/crawl_status*.json`
   这类运行态文件，避免旧机器队列/告警/状态在新服务器复活；
4. 写入 `manifest.json`（导出时间、git commit、各表行数、JSON 大小）。

完成后会打印一段类似：

```
===== 导出完成 =====
  bundle      : /xxx/dist/dataset_20260427_173000.tar.gz
  size        : 412M
  XHS 机会卡  : 510 张
  视觉策略包  : 5 个
  候选/Brief : 30/11
```

---

## 二、上传到服务器

```bash
scp dist/dataset_20260427_173000.tar.gz user@server:/tmp/
scp install.sh user@server:/tmp/        # 如尚未把仓库放到 /opt 上
```

---

## 三、服务器：一键安装 + 自动引入

> 假定客户侧已有 git 仓库放在 `/opt/ontology-os`（或重新 clone）。

```bash
cd /opt/ontology-os
git pull --ff-only
sudo bash install.sh \
  --bundle /tmp/dataset_20260427_173000.tar.gz \
  --bundle-mode safe
```

`install.sh` 会在所有服务安装结束、`post_install_smoke` 通过之后，
自动调用 `scripts/bootstrap_data.sh`：

1. 解包 tar.gz 到临时目录；
2. 校验 `manifest.json` 的 git_commit 是否与本地一致（不一致仅 warn）；
3. 如果带 `--restart-service`，会在覆盖 sqlite/json 前先 `systemctl stop ontology-os`；
4. `--mode safe` 把已存在文件改名为 `*.bak.<ts>` 后再写入；
5. 显式清理 `job_queue / alerts / crawl_status*` 等运行态文件；
6. 调 `python -m apps.intel_hub.scripts.bootstrap_data sync-cards`
   把 `opportunity_cards.json` 写入 `xhs_review.sqlite`；
7. 调 `python -m apps.intel_hub.scripts.bootstrap_data validate`
   校验关键 SQLite 表均可连通；
8. `systemctl restart ontology-os`。

如果其中任何一步失败，`install.sh --bundle ...` 会整体非零退出，不会把“数据导入失败”
伪装成“部署完成”。

如果不想在 install 阶段引入数据，也可以分步：

```bash
sudo bash install.sh                            # 先装基础
sudo bash scripts/bootstrap_data.sh \
  --bundle /tmp/dataset.tar.gz \
  --mode safe \
  --restart-service
```

### `--bundle-mode` 取值

| 值          | 行为                                        |
| ----------- | ------------------------------------------- |
| `safe`      | 已存在 → 改名 `*.bak.<ts>` 再写入（默认）    |
| `overwrite` | 直接覆盖（用于已知服务器数据可丢的情形）    |

---

## 四、可选：重建模式（不导入快照）

服务器侧已经配齐 LLM key（`.env` 中 `OPENAI_API_KEY` /
`DEEPSEEK_API_KEY` 等），希望从 raw jsonl 重新跑 pipeline：

```bash
sudo bash scripts/bootstrap_data.sh \
  --bundle /tmp/dataset.tar.gz \
  --rebuild \
  --restart-service
```

脚本会：

1. 仅解包 raw / fixtures / MediaCrawler jsonl（不动 sqlite）；
2. 调 `python -m apps.intel_hub.workflow.xhs_opportunity_pipeline ...`；
3. 调 `apps.intel_hub.workflow.refresh_pipeline.run_pipeline()`；
4. 主服务启动时自带 `sync_cards_from_json`，会把新 JSON 写入 sqlite。

> 注意：重建会真实调用 LLM/VLM，耗时和费用与本机首跑一致；快照模式可绕开。

---

## 五、验证

```bash
# 1. systemd 状态
sudo systemctl status ontology-os
sudo journalctl -u ontology-os -n 100 --no-pager

# 2. 主站可达
curl -I http://127.0.0.1:8000/

# 3. Python CLI 摘要
.venv/bin/python -m apps.intel_hub.scripts.bootstrap_data summary

# 4. 浏览器
#   /                          → 首页
#   /xhs-opportunities         → 机会卡列表，应显示导入的 N 张
#   /planning/<opportunity_id> → 内容策划工作台
#   /growth-lab/workspace      → 视觉无限画布
```

`summary` 命令会输出每个 sqlite 关键表行数 + JSON 文件大小，方便核验数据是否
按预期搬过来：

```
=== SQLite rows ===
  data/xhs_review.sqlite      xhs_opportunity_cards   510
  data/content_plan.sqlite    rule_specs              1392
  data/growth_lab.sqlite      visual_strategy_packs   5
  data/growth_lab.sqlite      strategy_candidates     30
...
```

---

## 六、安全与合规

- 默认排除 `data/sessions/*.session` 与 `browser_data/`，避免 cookie/登录态外泄；
  如确需可加 `--include-sessions`；
- 默认排除 `job_queue / alerts / crawl_status*` 这类运行态文件，只迁业务数据，不迁旧任务状态；
- `manifest.json` 内嵌 `git_commit`，服务器侧版本不一致时 bootstrap 仅 warn，
  方便预发/灰度场景；
- `.env` 不在 bundle 中，仍需在服务器手动准备；
- bundle 体积大时建议 `split -b 500M dataset.tar.gz dataset.tar.gz.part_`，
  服务器端 `cat dataset.tar.gz.part_* > dataset.tar.gz` 后再走 bootstrap。

---

## 七、常见问题

**Q：导入后机会卡列表仍为空？**
- 看 `bootstrap_data.py summary`，确认 `xhs_review.sqlite::xhs_opportunity_cards` 行数；
- 行数为 0 时手动跑 `python -m apps.intel_hub.scripts.bootstrap_data sync-cards`
  并查看是否报"找不到 opportunity_cards.json"；
- 检查 `data/output/xhs_opportunities/opportunity_cards.json` 是否存在。

**Q：Web 报 sqlite database is locked？**
- `--restart-service` 会自动先停服务再导入；如果你手动导入且没加这个参数，先 `systemctl stop ontology-os`。

**Q：`--mode safe` 会留一堆 .bak.* 文件？**
- 是。验证导入无误后可手动删除 `data/*.bak.*` 与 `data/output/.bak.*`。

**Q：服务器没有 sqlite3 命令？**
- bootstrap 阶段不强依赖 `sqlite3`，但建议安装；`install.sh` 已默认装 `libsqlite3-dev`，
  通过 `apt-get install -y sqlite3` 单独补一个 CLI 即可。
