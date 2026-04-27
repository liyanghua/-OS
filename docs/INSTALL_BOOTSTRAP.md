# Ubuntu 安装与数据初始化手册

本手册把客户侧 Ubuntu 服务器上的两件事串成一条完整流程：

1. 用 `install.sh` 把系统和第三方依赖装起来；
2. 用 bundle 或重建模式把业务数据初始化进去。

如果你的目标是“服务器不要依赖现场浏览器采集，也能先把系统跑起来并看到真实数据”，推荐默认走：

```bash
sudo bash install.sh --bundle data_sets/dataset.tar.gz --bundle-mode safe
```

它会先完成 Ubuntu 安装，再自动调用 `scripts/bootstrap_data.sh` 导入数据快照。

相关文档：

- 数据导出与迁移细节：`docs/CLIENT_DATA_MIGRATION.md`
- 当前部署实现记录：`docs/IMPLEMENT.md`

---

## 一、推荐使用场景

### 场景 A：首部署，不依赖现场采集

最推荐。

- 本机先导出一份数据快照；
- 服务器只负责安装和导入；
- 不需要服务器现场扫码登录浏览器；
- 页面打开后就能直接看到机会卡、规划工作台、视觉策略等已有数据。

### 场景 B：先装环境，稍后再导数据

适合：

- 运维先做系统安装；
- 数据包稍后再传；
- 需要先确认 Ubuntu 依赖和 systemd 没问题。

### 场景 C：服务器侧从 raw jsonl 重建

适合：

- 客户侧已经准备好 LLM key；
- 希望服务器自己从原始 jsonl 重跑 pipeline；
- 能接受额外耗时和 token 成本。

---

## 二、`install.sh` 实际做了什么

当前 `install.sh` 是 **Ubuntu-only** 部署脚本，默认针对 Ubuntu 22.04 / 24.04 家族。

主流程如下：

1. 检查 `/etc/os-release`，非 Ubuntu 直接失败。
2. 用 `apt-get` 安装基础依赖和 Playwright 运行库。
3. 检查并准备 `python3.11`、`python3.12`。
4. 创建三套独立虚拟环境：
   - 根目录 `.venv`：主站，Python 3.11
   - `third_party/MediaCrawler/.venv`：采集链，Python 3.11
   - `third_party/TrendRadar/.venv`：TrendRadar，Python 3.12
5. 安装主系统依赖：
   - 根仓库 `pip install -e "$REPO_ROOT[llm-all,browser,vision]"`
6. 处理第三方目录：
   - `third_party/TrendRadar` 不存在时自动 clone
   - 固定 checkout 到 pin commit
   - `third_party/MediaCrawler` 使用仓库现有目录
   - `third_party/deer-flow` / `third_party/hermes-agent` 不参与部署
7. 生成服务器运行配置：
   - `config/runtime.server.yaml`
   - `.env` 模板
   - 默认写入 `INTEL_HUB_RUNTIME_CONFIG=config/runtime.server.yaml`
   - 默认写入 `BROWSER_HEADLESS=true`
8. 导入登录态：
   - 如果传 `--sessions-dir`
   - 会复制 `xhs_state.json` / `dy_state.json` 及 meta 文件到 `data/sessions/`
   - 并把 `third_party/MediaCrawler/data/sessions` 对齐到根目录 sessions
9. 安装 systemd：
   - `ontology-os.service`
   - `ontology-trendradar.service`
   - `ontology-trendradar.timer`
10. 执行 smoke：
   - 主系统 compileall
   - `trendradar --help`
   - `legacy_intel_hub_runner.py --help`
11. 如果传了 `--bundle`，最后再自动做数据导入。

一句话总结：

`install.sh` 负责“把服务器环境和服务形态装好”，`bootstrap_data.sh` 负责“把业务数据搬进去”。

---

## 三、推荐首部署流程

这是最适合客户现场、也最不依赖浏览器采集的一条路径。

### 第 1 步：在本机导出数据快照

```bash
cd /path/to/-OS

# 全量导出到仓库内 data_sets/
bash scripts/export_dataset.sh --out data_sets/dataset.tar.gz

# 如果只要轻量包
# bash scripts/export_dataset.sh --lite --out data_sets/dataset.tar.gz
```

默认导出内容：

- 业务 SQLite
- `data/output/`
- `data/raw/` / `data/raw_lake/`
- `data/fixtures/`
- `third_party/MediaCrawler/data/{xhs,douyin}/jsonl`
- `manifest.json`

默认不会导出：

- `data/job_queue.json`
- `data/alerts.json`
- `data/crawl_status*.json`
- 浏览器运行态缓存

这样可以避免把旧机器的队列、告警、采集状态一并带到新机器。

### 第 2 步：确认服务器上的 bundle 路径

```bash
ls -lah data_sets/dataset.tar.gz
```

如果服务器仓库里已经有这份完整包，就直接使用 `data_sets/dataset.tar.gz`，
不需要再拷贝到 `/tmp/`。

只有在“本机导出后再上传到另一台服务器”的情况下，才需要类似：

```bash
scp data_sets/dataset.tar.gz user@server:/tmp/
```

### 第 3 步：服务器拉主线最新代码

```bash
cd /opt/ontology-os
git pull --ff-only
```

### 第 4 步：执行一键安装 + 自动导入

```bash
cd /opt/ontology-os
sudo bash install.sh \
  --bundle data_sets/dataset.tar.gz \
  --bundle-mode safe
```

这是默认推荐命令。

`--bundle-mode safe` 的行为是：

- 服务器上已有同名 sqlite / json / output 目录时；
- 先备份成 `*.bak.<ts>`；
- 再覆盖写入新数据。

如果你明确知道服务器上的旧数据可以直接丢弃，也可以用：

```bash
sudo bash install.sh \
  --bundle data_sets/dataset.tar.gz \
  --bundle-mode overwrite
```

---

## 四、安装完成后会得到什么

### 1. 主服务

- systemd 服务名：`ontology-os`
- 入口：`apps.intel_hub.api.server_entry`
- 默认监听：
  - `INTEL_HUB_HOST=0.0.0.0`
  - `INTEL_HUB_PORT=8000`

### 2. TrendRadar 定时任务

- `ontology-trendradar.service`
- `ontology-trendradar.timer`
- 默认每 30 分钟触发一次

### 3. 服务器运行配置

生成文件：

- `config/runtime.server.yaml`

核心约定：

- `trendradar_output_dir: third_party/TrendRadar/output`
- `embedded_crawl_worker_enabled: true`
- `mediacrawler_sources` 指向 `third_party/MediaCrawler/data/...`
- 不再使用开发机绝对路径

### 4. `.env` 模板

如果仓库里不存在 `.env`，脚本会生成模板，但不会替你填真实 key。

必备层：

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

增强层：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `ANTHROPIC_API_KEY`

图像 / 视觉层：

- `OPENROUTER_API_KEY`
- `IMAGE_GEN_OPENAI_BASE_URL`
- `OPENROUTER_IMAGE_MODEL`
- `OPENROUTER_GPT5_IMAGE_KEY`
- `DASHSCOPE_API_KEY`

没有 key 不会阻断安装，但会影响对应能力。

### 5. LLM key 实际怎么配

服务器上实际编辑的是仓库根目录：

- `/opt/ontology-os/.env`

推荐做法：

```bash
cd /opt/ontology-os
sudo nano .env
```

如果是第一次安装、`install.sh` 已自动生成 `.env` 模板，直接把真实值填进去即可。

一个可直接改的示例如下：

```dotenv
# ===== 必备 LLM =====
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini

# ===== 增强 =====
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
ANTHROPIC_API_KEY=

# ===== 图像 / 视觉 =====
OPENROUTER_API_KEY=
IMAGE_GEN_OPENAI_BASE_URL=https://singapore.zw-ai.com/api/v1
OPENROUTER_IMAGE_MODEL=google/gemini-2.5-flash-image
OPENROUTER_GPT5_IMAGE_KEY=
DASHSCOPE_API_KEY=

# ===== 部署运行 =====
INTEL_HUB_RUNTIME_CONFIG=config/runtime.server.yaml
BROWSER_HEADLESS=true
INTEL_HUB_HOST=0.0.0.0
INTEL_HUB_PORT=8000
```

建议按下面这个优先级理解：

- 只想“装起来 + 导入已有数据 + 看页面”：
  - 严格来说可以先不填 key
  - 但所有依赖 LLM / VLM 的链路都会降级或不可用
- 最小推荐配置：
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
- 想要 DeepSeek 作为补充模型：
  - `DEEPSEEK_API_KEY`
  - `DEEPSEEK_MODEL`
- 想要 Anthropic 能力：
  - `ANTHROPIC_API_KEY`
- 想要图片 / 视频 / 视觉生成：
  - `OPENROUTER_API_KEY`，或
  - `OPENAI_API_KEY` + `IMAGE_GEN_OPENAI_BASE_URL`
  - `OPENROUTER_IMAGE_MODEL`
  - 或 `DASHSCOPE_API_KEY`

### 6. 不同 key 分别影响什么

- `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL`
  - 主 LLM 链路默认推荐配置
  - 内容策划、文本生成、部分 AI 工作台能力通常优先依赖这一层
- `IMAGE_GEN_OPENAI_BASE_URL`
  - 只作用于图片生成链路，不影响文本 LLM 路由
  - 设成 `https://singapore.zw-ai.com/api/v1` 后，图片通道改为复用 `OPENAI_API_KEY`
  - 留空时继续默认走 OpenRouter
- `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL`
  - DeepSeek 路由与补充推理链路
- `ANTHROPIC_API_KEY`
  - Anthropic 路由能力
- `OPENROUTER_API_KEY`
  - 默认图片网关未切换时的图像/视觉认证
- `OPENROUTER_IMAGE_MODEL`
  - 当前图片链路统一使用的模型名；默认网关和自定义图片网关都继续读取它
- `OPENROUTER_GPT5_IMAGE_KEY`
  - 图像链路扩展 key，按当前模板保留
- `DASHSCOPE_API_KEY`
  - DashScope 图像 / 视觉 / 参考图优先链路

更实用地说：

- 你当前这轮“从 bundle 首装并看已有数据”，最关键的是系统和数据先起来；
- 如果还没准备好 key，不会阻断安装；
- 但如果你接下来要测内容策划、视觉生成、raw 重建、图像分析，再补 key 会更稳。

### 7. 改完 `.env` 之后要做什么

改完 key 之后，建议执行：

```bash
cd /opt/ontology-os
sudo systemctl restart ontology-os
bash install.sh --doctor
```

`--doctor` 不会打印敏感值本身，只会显示：

- `SET`
- `MISSING`

比如你希望看到：

```text
== LLM Keys ==
OPENAI_BASE_URL: SET
OPENAI_API_KEY: SET
OPENAI_MODEL: SET
DEEPSEEK_API_KEY: MISSING
IMAGE_GEN_OPENAI_BASE_URL: SET
OPENROUTER_API_KEY: MISSING
DASHSCOPE_API_KEY: MISSING
```

如果 `IMAGE_GEN_OPENAI_BASE_URL` 显示 `MISSING`，含义是“图片链路仍走默认 OpenRouter”，
不是错误。

如果你后面要测试 raw 重建，也建议顺手再执行：

```bash
sudo journalctl -u ontology-os -n 100 --no-pager
```

看服务启动后有没有因为 key 缺失出现明显告警。

---

## 五、数据初始化有哪几种做法

### 方式 1：安装时一并导入

最推荐：

```bash
sudo bash install.sh --bundle data_sets/dataset.tar.gz --bundle-mode safe
```

安装顺序是：

1. Ubuntu 依赖安装完成
2. venv 和第三方依赖安装完成
3. systemd 服务完成
4. smoke 通过
5. 才开始导入 bundle

导入时会：

1. 解包 bundle
2. 校验 manifest
3. 先停 `ontology-os`
4. 导入 sqlite / output / raw / fixtures / MediaCrawler jsonl
5. 清理 `job_queue / alerts / crawl_status*`
6. `sync-cards`
7. `validate`
8. 重启 `ontology-os`

如果任一步失败，`install.sh` 会整体非零退出。

### 方式 2：安装后单独导入

适合分步执行：

```bash
sudo bash install.sh

sudo bash scripts/bootstrap_data.sh \
  --bundle data_sets/dataset.tar.gz \
  --mode safe \
  --restart-service
```

这种方式更适合：

- 运维先装环境；
- 业务侧稍后再给数据；
- 或你想单独重试数据导入，而不重装环境。

### 方式 3：用 raw jsonl 重建

```bash
sudo bash scripts/bootstrap_data.sh \
  --bundle data_sets/dataset.tar.gz \
  --rebuild \
  --restart-service
```

这条路径不会恢复原始 sqlite 快照，而是：

1. 只解出 raw / fixtures / MediaCrawler jsonl
2. 在服务器上重新跑 pipeline
3. 再把新产出的 JSON 同步入 sqlite

注意：

- 这会真实调用 LLM / VLM；
- 依赖服务器 `.env` 已配置好相关 key；
- 耗时和成本高于快照模式。

---

## 六、如果不想依赖浏览器采集，应该怎么做

建议遵循下面的原则：

1. 首部署优先走 bundle 快照，不走服务器现场采集。
2. 没有登录态也没关系，主站和 TrendRadar 可以正常运行。
3. 不导入 `data/sessions` 时，采集能力会处于“待导入登录态”状态。
4. 当前服务器模式默认 `BROWSER_HEADLESS=true`，但这不等于“无浏览器依赖就能采集”。
5. 如果你根本不需要服务器点“数据采集”，那就不要把首部署成功与浏览器采集绑定在一起。

更直白地说：

- “系统可用” 和 “服务器可做浏览器采集” 是两件事；
- 当前推荐先确保前者；
- 后者后续再补登录态和采集链调试。

---

## 七、常用命令

### 环境巡检

```bash
bash install.sh --doctor
```

会检查：

- Ubuntu 版本
- Python 3.11 / 3.12
- 三套 venv 状态
- TrendRadar / MediaCrawler 是否存在
- sessions 是否导入
- `runtime.server.yaml` 是否存在
- LLM key 缺失项

### 查看主服务

```bash
sudo systemctl status ontology-os
sudo journalctl -u ontology-os -n 200 --no-pager
sudo journalctl -u ontology-os -f
```

### 查看 TrendRadar

```bash
sudo systemctl status ontology-trendradar.timer
sudo journalctl -u ontology-trendradar.service -n 200 --no-pager
```

### 查看数据摘要

```bash
.venv/bin/python -m apps.intel_hub.scripts.bootstrap_data summary
```

### 手动校验 manifest

```bash
.venv/bin/python -m apps.intel_hub.scripts.bootstrap_data manifest --path /tmp/manifest.json
```

---

## 八、安装后的验证步骤

建议按这个顺序验证：

### 1. systemd

```bash
sudo systemctl status ontology-os
sudo systemctl status ontology-trendradar.timer
```

### 2. HTTP 可达

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/crawl-status
curl -I http://127.0.0.1:8000/alerts
```

### 3. CLI 摘要

```bash
.venv/bin/python -m apps.intel_hub.scripts.bootstrap_data summary
```

### 4. 页面检查

至少看这几个页面：

- `/`
- `/xhs-opportunities`
- `/planning/<opportunity_id>`
- `/growth-lab/workspace`

如果走的是 bundle 快照模式，`/xhs-opportunities` 应该能直接看到导入的真实机会卡。

---

## 九、升级已有服务器时怎么做

### 仅更新代码和环境

```bash
cd /opt/ontology-os
git pull --ff-only
sudo bash install.sh --skip-apt
```

适合：

- 系统依赖已经就绪；
- 本次只更新代码、venv、systemd、runtime 配置。

### 更新代码并重新导入新数据快照

```bash
cd /opt/ontology-os
git pull --ff-only
sudo bash install.sh \
  --skip-apt \
  --bundle data_sets/dataset.tar.gz \
  --bundle-mode safe
```

### 不重装，只重新导数据

```bash
cd /opt/ontology-os
sudo bash scripts/bootstrap_data.sh \
  --bundle data_sets/dataset.tar.gz \
  --mode safe \
  --restart-service
```

---

## 十、常见问题

### Q1：没有 `--sessions-dir`，安装能成功吗？

能。

- 安装不会因为缺登录态而失败；
- 主站和 TrendRadar 仍可运行；
- 但浏览器采集相关能力会提示先导入登录态。

### Q2：为什么 bundle 不导出 `job_queue` 和 `crawl_status`？

因为这些是运行态，不是业务事实数据。

如果把它们也迁过去，容易出现：

- 旧任务在新机器“复活”
- 旧告警继续显示
- 旧采集状态误导当前环境

### Q3：为什么导入前要先停 `ontology-os`？

因为导入会覆盖 sqlite 和 JSON。

如果服务还在运行，容易出现：

- `sqlite database is locked`
- 文件部分覆盖
- 页面读到一半旧数据、一半新数据

### Q4：什么时候用 `safe`，什么时候用 `overwrite`？

默认一律用 `safe`。

只有在你明确知道：

- 目标服务器没有需要保留的旧数据；
- 或你已经做过备份；

才建议用 `overwrite`。

### Q5：什么时候需要 `--skip-mediacrawler`？

只有在你确认这台服务器完全不需要采集链时再用。

默认不建议跳过，因为当前架构里主站的采集 worker 仍然会依赖 MediaCrawler 目录和 venv。

---

## 十一、最小命令清单

### 本机

```bash
bash scripts/export_dataset.sh --out data_sets/dataset.tar.gz
```

### 服务器

```bash
cd /opt/ontology-os
git pull --ff-only
sudo bash install.sh --bundle data_sets/dataset.tar.gz --bundle-mode safe
```

### 验证

```bash
sudo systemctl status ontology-os
curl -I http://127.0.0.1:8000/
.venv/bin/python -m apps.intel_hub.scripts.bootstrap_data summary
```

如果这三步都正常，基本就说明“Ubuntu 安装 + 数据初始化”已经跑通。
