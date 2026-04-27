# `install.sh` 全家桶服务器一键部署升级方案

## 摘要

把当前 `install.sh` 从“单一 FastAPI 进程安装脚本”升级为“Ubuntu 纯命令行服务器原生部署器”，目标是一次性完成主系统、`TrendRadar`、`MediaCrawler` 运行环境和 systemd 编排，同时把第三方依赖、浏览器登录态、LLM key、Python 版本、虚拟环境这些高风险点收敛掉。

这次部署只交付当前真实运行主线：`apps/intel_hub` 的 FastAPI/Jinja 工作台 + 同机 `TrendRadar` 数据源 + 同机按任务触发的 `MediaCrawler`。根目录 `src/` 的 Next.js 原型不纳入默认部署，不再在 `install.sh` 里无条件执行 `npm install && npm run build`。

## 关键改动

### 1. 运行时拆分与版本固定

- 主系统保留根目录 `.venv`，固定用 Python `3.11`，负责 `apps/intel_hub`、`apps/content_planning`、`apps/growth_lab`。
- `third_party/MediaCrawler/.venv` 固定用 Python `3.11`，继续走现有 `legacy_intel_hub_runner.py` 子进程模式。
- `third_party/TrendRadar/.venv` 固定用 Python `3.12`，避免和主系统、MediaCrawler 混装。
- `install.sh` 需要显式探测并校验 `python3.11` 和 `python3.12`，找不到时安装对应 `venv/dev` 包；不再尝试“一套 Python 跑全栈”。

### 2. `install.sh` CLI 与部署行为重构

- 保留现有 `--repo --branch --dir --host --port --env-file` 等参数。
- 新增 `--profile full` 作为默认全家桶模式。
- 新增 `--sessions-dir <path>`，用于导入本机准备好的 `xhs_state.json` / `dy_state.json` 及其 `.meta.json`。
- 新增 `--skip-trendradar`、`--skip-mediacrawler`，便于降级部署。
- 新增 `--trendradar-on-calendar`，默认 `*:0/30`，为 `TrendRadar` 建立 systemd timer。
- 新增 `--runtime-config-out`，默认生成 `config/runtime.server.yaml`，不直接依赖仓库内开发态 `config/runtime.yaml`。
- 新增 `--doctor` 或等价预检模式，输出 Python/venv/Playwright/key/session/third_party 检查结果但不改动系统。

### 3. 第三方依赖治理

- `TrendRadar` 由于不在仓库受控内容里，部署时若缺失则自动 clone 到 `third_party/TrendRadar`，并固定到当前已验证 commit `b1d09d08ea27e67382c044ba67bbb0af2fd8a979`。
- `MediaCrawler` 使用仓库内已有代码，不再要求额外 clone，但安装时要按上游推荐完成依赖和 Playwright Chromium。
- `third_party/deer-flow`、`third_party/hermes-agent` 不纳入 install 路径，只保留原状。

### 4. 服务器专用运行配置

- 不再直接使用当前开发机 `config/runtime.yaml`，改为部署时生成 `config/runtime.server.yaml`。
- 生成后的 server runtime 只保留服务器可用的相对路径，清空/禁用本机绝对路径 `xhs_sources`，保留：
  - `trendradar_output_dir: third_party/TrendRadar/output`
  - `mediacrawler_sources: third_party/MediaCrawler/data/...`
  - `embedded_crawl_worker_enabled: true`
- 主服务启动时通过新环境变量 `INTEL_HUB_RUNTIME_CONFIG` 指向 server runtime，而不是写死默认配置。

### 5. 启动入口与 systemd 编排

- 新增一个专用服务器启动入口，读取 `INTEL_HUB_RUNTIME_CONFIG` 后启动 Uvicorn；不再依赖 `uvicorn ...:create_app --factory` 的无参形式。
- 建立 `ontology-os.service` 作为主站服务。
- 建立 `ontology-trendradar.service` + `ontology-trendradar.timer`，定时产出 `TrendRadar` output。
- 不创建独立 `MediaCrawler` 常驻服务；它继续由主站内嵌队列 worker 按任务拉起。
- 主站 service 注入 `BROWSER_HEADLESS=true` 一类服务器模式环境变量。

### 6. 浏览器登录态与会话目录对齐

- `install.sh` 支持把 `--sessions-dir` 中的登录态复制到根目录 `data/sessions/`。
- 如果存在 `xhs_state.json.meta.json` 一并导入，保留过期时间信息。
- 自动补齐或刷新 `data/sessions/session_registry.json` 的默认记录。
- 强制把 `third_party/MediaCrawler/data/sessions` 对齐到根目录 `data/sessions`，优先采用 symlink，避免“主系统已登录但 MediaCrawler 看不到登录态”。
- 如果没有导入登录态，部署成功但给出强告警，不阻断主系统和 TrendRadar 启动。

### 7. LLM Key 策略

- `install.sh` 不回显 key，不把 key 打进日志。
- `.env` 模板按“必备/增强/可选”分组生成：
  - 主文本能力：`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`
  - 增强 fallback：`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`、`ANTHROPIC_API_KEY`
  - 图像/视频/视觉分析：`OPENROUTER_API_KEY`、`OPENROUTER_IMAGE_MODEL`、`DASHSCOPE_API_KEY`
- 缺 key 不阻断安装，但在总结里输出能力降级矩阵。
- 根 `pyproject.toml` 需要补齐服务器真实会用到的可选依赖，至少让 `browser` extra 和 `dashscope` 这类运行期依赖可被脚本一次装全。

### 8. 纯 CLI 服务器兼容性修正

- 服务器部署默认把采集浏览器切到 headless，不再沿用当前 `payload.get("headless", False)` 的 GUI 默认值。
- 主站入队采集时在未显式传入 `headless` 的情况下，默认读取服务器环境变量并走 headless。
- 小红书发布/回采等 Playwright 服务同样读取服务器 headless 配置。
- 服务器模式下，扫码登录 API 应明确返回“不支持现场扫码，请导入登录态”而不是盲目拉 GUI。

### 9. 文档与进度回写

- 实现完成后更新根 `IMPLEMENT.md`，记录新的部署架构、Python/venv 划分、登录态导入方式、TrendRadar pin、systemd 服务名。
- 如果 `intel_hub` 文档中涉及部署入口或 runtime 路径，也同步更新 `docs/IMPLEMENT.md` 的相关进度备注。

## 公共接口/约定变化

- `install.sh` 新增 `--profile full`、`--sessions-dir`、`--skip-trendradar`、`--skip-mediacrawler`、`--trendradar-on-calendar`、`--runtime-config-out`、`--doctor`。
- 新增环境变量约定：`INTEL_HUB_RUNTIME_CONFIG`、`BROWSER_HEADLESS=true`。
- 新增部署产物：`config/runtime.server.yaml`、`ontology-os.service`、`ontology-trendradar.service`、`ontology-trendradar.timer`。
- 主服务默认不再构建 Next.js 原型。

## 测试与验收

- `bash -n install.sh` 通过，`--help` 覆盖所有新参数。
- `--doctor` 在无 key、无登录态、缺第三方目录时能给出正确诊断。
- 主系统环境创建后，`python -c "from apps.intel_hub.api.app import create_app; create_app(...)"` 成功。
- `third_party/TrendRadar/.venv/bin/python -m trendradar --help` 成功。
- `third_party/MediaCrawler/.venv/bin/python third_party/MediaCrawler/legacy_intel_hub_runner.py --help` 成功。
- 登录态导入后，根目录 `data/sessions/xhs_state.json` 与 `third_party/MediaCrawler/data/sessions/xhs_state.json` 指向同一份数据。
- 主服务启动后，首页和 `/crawl-status`、`/alerts` 返回 200。
- 在无登录态情况下，主服务和 TrendRadar 可正常启动，采集功能明确告警。
- 在有登录态情况下，创建一次 `/crawl-jobs` 后，主站内嵌 worker 能拉起 MediaCrawler 子进程并写出 `third_party/MediaCrawler/data/xhs/jsonl` 结果。

## 假设与默认值

- 目标服务器是 Ubuntu 纯命令行环境。
- 对外暴露方式为端口直出，不在本轮自动接 Nginx/Caddy/HTTPS。
- 登录态采用“导入本机已准备好的 state 文件”，不是服务器现场扫码。
- 缺少登录态时“部署成功但采集告警”，不是整体失败。
- `TrendRadar` 作为数据源同机运行并默认建立 30 分钟 timer；`MediaCrawler` 不做常驻服务。
- 默认部署主线是 FastAPI 工作台，不包含 Next.js 原型前台。
