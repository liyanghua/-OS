#!/usr/bin/env bash
# Ubuntu one-shot deployment for Ontology Intel Hub + MediaCrawler + TrendRadar.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

APP_SERVICE_NAME="ontology-os"
TRENDRADAR_SERVICE_NAME="ontology-trendradar"
TRENDRADAR_TIMER_NAME="ontology-trendradar.timer"
TRENDRADAR_REPO_URL="https://github.com/sansan0/TrendRadar.git"
TRENDRADAR_PIN_COMMIT="b1d09d08ea27e67382c044ba67bbb0af2fd8a979"
DEFAULT_RUNTIME_CONFIG_OUT="config/runtime.server.yaml"
DEFAULT_TRENDRADAR_ON_CALENDAR="*:0/30"

APP_VENV="$REPO_ROOT/.venv"
MC_ROOT="$REPO_ROOT/third_party/MediaCrawler"
MC_VENV="$MC_ROOT/.venv"
TR_ROOT="$REPO_ROOT/third_party/TrendRadar"
TR_VENV="$TR_ROOT/.venv"
SESSIONS_DIR="$REPO_ROOT/data/sessions"
MC_SESSIONS_DIR="$MC_ROOT/data/sessions"
SYSTEMD_DIR="$REPO_ROOT/deploy/systemd"
APP_UNIT_OUT="$SYSTEMD_DIR/${APP_SERVICE_NAME}.service"
TR_SERVICE_OUT="$SYSTEMD_DIR/${TRENDRADAR_SERVICE_NAME}.service"
TR_TIMER_OUT="$SYSTEMD_DIR/${TRENDRADAR_TIMER_NAME}"

SKIP_APT=0
SKIP_TRENDRADAR=0
SKIP_MEDIACRAWLER=0
DOCTOR_ONLY=0
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
RUN_USER="${SUDO_USER:-${USER:-root}}"
SESSIONS_IMPORT_DIR=""
RUNTIME_CONFIG_OUT="$DEFAULT_RUNTIME_CONFIG_OUT"
TRENDRADAR_ON_CALENDAR="$DEFAULT_TRENDRADAR_ON_CALENDAR"
DATA_BUNDLE=""
DATA_BUNDLE_MODE="safe"

if [[ -t 1 ]]; then
  C_RED="\033[31m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_RESET="\033[0m"
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_RESET=""
fi
log() { echo -e "${C_BLUE}[INFO]${C_RESET} $*"; }
ok() { echo -e "${C_GREEN}[ OK ]${C_RESET} $*"; }
warn() { echo -e "${C_YELLOW}[WARN]${C_RESET} $*"; }
err() { echo -e "${C_RED}[FAIL]${C_RESET} $*" >&2; }
die() { err "$*"; exit 1; }

trap 'err "install.sh 失败，行号: $LINENO"' ERR

usage() {
  cat <<'EOF'
用法:
  bash install.sh [options]

选项:
  --sessions-dir <path>          导入已有 storage_state 目录
  --skip-trendradar              跳过 TrendRadar clone/install/systemd
  --skip-mediacrawler            跳过 MediaCrawler venv/install
  --skip-apt                     跳过 apt 依赖安装
  --trendradar-on-calendar <v>   覆盖 TrendRadar systemd timer OnCalendar，默认 *:0/30
  --runtime-config-out <path>    覆盖 runtime.server.yaml 输出位置
  --doctor                       只做环境巡检，不做安装
  --port <port>                  主站监听端口，默认 8000
  --host <host>                  主站监听地址，默认 0.0.0.0
  --bundle <tar.gz>              安装完成后自动导入由 scripts/export_dataset.sh
                                 在本机产出的数据快照（免浏览器采集即可起服务）
  --bundle-mode <safe|overwrite> 已存在文件的处理策略，默认 safe（备份后覆盖）
  -h, --help                     显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sessions-dir) SESSIONS_IMPORT_DIR="$2"; shift 2 ;;
    --skip-trendradar) SKIP_TRENDRADAR=1; shift ;;
    --skip-mediacrawler) SKIP_MEDIACRAWLER=1; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
    --trendradar-on-calendar) TRENDRADAR_ON_CALENDAR="$2"; shift 2 ;;
    --runtime-config-out) RUNTIME_CONFIG_OUT="$2"; shift 2 ;;
    --doctor) DOCTOR_ONLY=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --bundle) DATA_BUNDLE="$2"; shift 2 ;;
    --bundle-mode) DATA_BUNDLE_MODE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "未知参数: $1" ;;
  esac
done

if [[ $EUID -eq 0 ]]; then
  SUDO=""
else
  command -v sudo >/dev/null 2>&1 || die "需要 root 或 sudo 权限"
  SUDO="sudo"
fi

APP_ENV_FILE="$REPO_ROOT/.env"
RUNTIME_CONFIG_PATH="$REPO_ROOT/$RUNTIME_CONFIG_OUT"

APT_PACKAGES=(
  git curl ca-certificates build-essential pkg-config libssl-dev libffi-dev
  libsqlite3-dev python3-venv python3-dev unzip software-properties-common
)
PLAYWRIGHT_PACKAGES=(
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxfixes3
  libxrandr2 libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 libgtk-3-0
  libx11-xcb1 libxcb1 libxext6 libxshmfence1
)

require_repo_root() {
  [[ -f "$REPO_ROOT/pyproject.toml" ]] || die "请在仓库根目录执行 install.sh"
  [[ -d "$REPO_ROOT/apps/intel_hub" ]] || die "未找到 apps/intel_hub"
}

check_ubuntu() {
  [[ -f /etc/os-release ]] || die "缺少 /etc/os-release，无法确认系统"
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || die "当前脚本仅支持 Ubuntu，检测到: ${PRETTY_NAME:-unknown}"
  ok "系统检测通过: ${PRETTY_NAME:-Ubuntu}"
}

apt_install() {
  if [[ "$SKIP_APT" -eq 1 ]]; then
    warn "跳过 apt 安装 (--skip-apt)"
    return
  fi
  log "安装 Ubuntu 基础依赖与 Playwright 运行库"
  $SUDO apt-get update -y
  $SUDO apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}" "${PLAYWRIGHT_PACKAGES[@]}"
}

ensure_python311() {
  if command -v python3.11 >/dev/null 2>&1; then
    return
  fi
  log "安装 Python 3.11"
  $SUDO apt-get install -y python3.11 python3.11-venv python3.11-dev
}

ensure_python312() {
  if command -v python3.12 >/dev/null 2>&1; then
    return
  fi
  log "安装 Python 3.12"
  if ! $SUDO apt-get install -y python3.12 python3.12-venv python3.12-dev; then
    warn "Ubuntu 默认源缺少 Python 3.12，尝试 deadsnakes"
    $SUDO add-apt-repository -y ppa:deadsnakes/ppa
    $SUDO apt-get update -y
    $SUDO apt-get install -y python3.12 python3.12-venv python3.12-dev || \
      die "安装 python3.12 失败，请手动准备后重试"
  fi
}

ensure_python_binaries() {
  ensure_python311
  ensure_python312
  command -v python3.11 >/dev/null 2>&1 || die "缺少 python3.11"
  command -v python3.12 >/dev/null 2>&1 || die "缺少 python3.12"
  ok "Python 3.11 / 3.12 已就绪"
}

create_venv_if_missing() {
  local py_bin="$1"
  local venv_dir="$2"
  if [[ ! -d "$venv_dir" ]]; then
    log "创建虚拟环境: $venv_dir"
    "$py_bin" -m venv "$venv_dir"
  fi
}

install_root_venv() {
  create_venv_if_missing python3.11 "$APP_VENV"
  "$APP_VENV/bin/python" -m pip install --upgrade pip wheel setuptools
  log "安装主系统依赖"
  "$APP_VENV/bin/pip" install -e "$REPO_ROOT[llm-all,browser,vision]"
}

ensure_trendradar_repo() {
  [[ "$SKIP_TRENDRADAR" -eq 1 ]] && return
  mkdir -p "$REPO_ROOT/third_party"
  if [[ ! -d "$TR_ROOT/.git" ]]; then
    log "克隆 TrendRadar"
    git clone "$TRENDRADAR_REPO_URL" "$TR_ROOT"
  fi
  git -C "$TR_ROOT" fetch --all --tags
  git -C "$TR_ROOT" checkout "$TRENDRADAR_PIN_COMMIT"
}

install_trendradar_venv() {
  [[ "$SKIP_TRENDRADAR" -eq 1 ]] && return
  create_venv_if_missing python3.12 "$TR_VENV"
  "$TR_VENV/bin/python" -m pip install --upgrade pip wheel setuptools
  log "安装 TrendRadar 依赖"
  "$TR_VENV/bin/pip" install -e "$TR_ROOT"
}

install_mediacrawler_venv() {
  [[ "$SKIP_MEDIACRAWLER" -eq 1 ]] && return
  [[ -d "$MC_ROOT" ]] || die "缺少 third_party/MediaCrawler"
  create_venv_if_missing python3.11 "$MC_VENV"
  "$MC_VENV/bin/python" -m pip install --upgrade pip wheel setuptools
  log "安装 MediaCrawler 依赖"
  "$MC_VENV/bin/pip" install -e "$MC_ROOT"
  "$MC_VENV/bin/python" -m playwright install chromium
}

ensure_runtime_dirs() {
  mkdir -p "$SESSIONS_DIR" "$REPO_ROOT/data/logs" "$REPO_ROOT/data/raw" "$REPO_ROOT/data/output"
  mkdir -p "$SYSTEMD_DIR"
}

render_runtime_server_yaml() {
  mkdir -p "$(dirname "$RUNTIME_CONFIG_PATH")"
  cat > "$RUNTIME_CONFIG_PATH" <<EOF
trendradar_output_dir: third_party/TrendRadar/output
storage_path: data/intel_hub.sqlite
b2b_platform_db_path: data/b2b_platform.sqlite
job_queue_path: data/job_queue.json
crawl_status_path: data/crawl_status.json
alerts_path: data/alerts.json
embedded_crawl_worker_enabled: true
default_page_size: 20
fixture_fallback_dir: data/fixtures/trendradar_output/output
raw_snapshot_dir: data/raw
include_rss: true
mediacrawler_sources:
  - enabled: true
    platform: xiaohongshu
    output_path: third_party/MediaCrawler/data/xhs/jsonl
    fixture_fallback: data/fixtures/mediacrawler_output/xhs/jsonl
  - enabled: true
    platform: douyin
    output_path: third_party/MediaCrawler/data/douyin/jsonl
EOF
  ok "已生成服务器运行配置: $RUNTIME_CONFIG_PATH"
}

ensure_env_template() {
  if [[ -f "$APP_ENV_FILE" ]]; then
    ok ".env 已存在，保留现有配置"
    return
  fi
  cat > "$APP_ENV_FILE" <<EOF
# ===== 必备 LLM =====
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# ===== 增强 =====
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat
ANTHROPIC_API_KEY=

# ===== 图像 / 视觉 =====
OPENROUTER_API_KEY=
OPENROUTER_IMAGE_MODEL=google/gemini-2.5-flash-image
DASHSCOPE_API_KEY=

# ===== 部署运行 =====
INTEL_HUB_RUNTIME_CONFIG=$RUNTIME_CONFIG_OUT
BROWSER_HEADLESS=true
INTEL_HUB_HOST=$HOST
INTEL_HUB_PORT=$PORT
EOF
  chmod 600 "$APP_ENV_FILE"
  warn "已生成 .env 模板，请补充真实密钥"
}

copy_session_file_if_exists() {
  local source_dir="$1"
  local filename="$2"
  if [[ -f "$source_dir/$filename" ]]; then
    cp "$source_dir/$filename" "$SESSIONS_DIR/$filename"
  fi
}

import_sessions_if_needed() {
  if [[ -z "$SESSIONS_IMPORT_DIR" ]]; then
    warn "未提供 --sessions-dir，采集能力将保持待导入登录态"
    return
  fi
  [[ -d "$SESSIONS_IMPORT_DIR" ]] || die "--sessions-dir 不存在: $SESSIONS_IMPORT_DIR"
  mkdir -p "$SESSIONS_DIR"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "xhs_state.json"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "xhs_state.meta.json"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "xhs_state.json.meta.json"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "dy_state.json"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "dy_state.meta.json"
  copy_session_file_if_exists "$SESSIONS_IMPORT_DIR" "dy_state.json.meta.json"
  ok "登录态导入完成: $SESSIONS_DIR"
}

align_mediacrawler_sessions_dir() {
  [[ "$SKIP_MEDIACRAWLER" -eq 1 ]] && return
  mkdir -p "$(dirname "$MC_SESSIONS_DIR")"
  if [[ -L "$MC_SESSIONS_DIR" || -d "$MC_SESSIONS_DIR" ]]; then
    rm -rf "$MC_SESSIONS_DIR"
  fi
  if ln -s "$SESSIONS_DIR" "$MC_SESSIONS_DIR" 2>/dev/null; then
    ok "MediaCrawler sessions 已通过 symlink 对齐"
    return
  fi
  warn "symlink 失败，回退为复制 sessions 目录"
  mkdir -p "$MC_SESSIONS_DIR"
  cp -R "$SESSIONS_DIR"/. "$MC_SESSIONS_DIR"/ 2>/dev/null || true
}

write_systemd_units() {
  cat > "$APP_UNIT_OUT" <<EOF
[Unit]
Description=Ontology Intel Hub
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_ROOT
EnvironmentFile=$APP_ENV_FILE
ExecStart=$APP_VENV/bin/python -m apps.intel_hub.api.server_entry
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  if [[ "$SKIP_TRENDRADAR" -eq 0 ]]; then
    cat > "$TR_SERVICE_OUT" <<EOF
[Unit]
Description=TrendRadar Batch Runner
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$RUN_USER
WorkingDirectory=$TR_ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$TR_VENV/bin/python -m trendradar
StandardOutput=journal
StandardError=journal
EOF

    cat > "$TR_TIMER_OUT" <<EOF
[Unit]
Description=TrendRadar schedule

[Timer]
OnCalendar=$TRENDRADAR_ON_CALENDAR
Persistent=true
Unit=$TRENDRADAR_SERVICE_NAME.service

[Install]
WantedBy=timers.target
EOF
  fi
}

install_systemd_units() {
  command -v systemctl >/dev/null 2>&1 || {
    warn "系统无 systemd，跳过服务注册"
    return
  }
  write_systemd_units
  $SUDO cp "$APP_UNIT_OUT" "/etc/systemd/system/${APP_SERVICE_NAME}.service"
  if [[ "$SKIP_TRENDRADAR" -eq 0 ]]; then
    $SUDO cp "$TR_SERVICE_OUT" "/etc/systemd/system/${TRENDRADAR_SERVICE_NAME}.service"
    $SUDO cp "$TR_TIMER_OUT" "/etc/systemd/system/${TRENDRADAR_TIMER_NAME}"
  fi
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable "$APP_SERVICE_NAME"
  $SUDO systemctl restart "$APP_SERVICE_NAME"
  if [[ "$SKIP_TRENDRADAR" -eq 0 ]]; then
    $SUDO systemctl enable "${TRENDRADAR_TIMER_NAME}"
    $SUDO systemctl restart "${TRENDRADAR_TIMER_NAME}"
  fi
}

check_python_line() {
  local name="$1"
  local bin="$2"
  if command -v "$bin" >/dev/null 2>&1; then
    echo "$name: $("$bin" --version 2>&1)"
  else
    echo "$name: MISSING"
  fi
}

check_venv_line() {
  local name="$1"
  local path="$2"
  if [[ -x "$path/bin/python" ]]; then
    echo "$name: READY ($("$path/bin/python" --version 2>&1))"
  else
    echo "$name: MISSING"
  fi
}

llm_key_status() {
  local key="$1"
  if [[ -n "${!key:-}" ]]; then
    echo "$key: SET"
  else
    echo "$key: MISSING"
  fi
}

run_doctor() {
  check_ubuntu
  cat <<EOF
== Ubuntu ==
$(grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"')

== Python ==
$(check_python_line "python3.11" "python3.11")
$(check_python_line "python3.12" "python3.12")

== Virtualenv ==
$(check_venv_line "root .venv" "$APP_VENV")
$(check_venv_line "MediaCrawler .venv" "$MC_VENV")
$(check_venv_line "TrendRadar .venv" "$TR_VENV")

== Third Party ==
TrendRadar: $( [[ -d "$TR_ROOT" ]] && echo "PRESENT" || echo "MISSING" )
MediaCrawler: $( [[ -d "$MC_ROOT" ]] && echo "PRESENT" || echo "MISSING" )

== Browser / Playwright ==
Chromium driver: $( [[ -x "$MC_VENV/bin/playwright" ]] && echo "READY" || echo "MISSING" )
Headless default: ${BROWSER_HEADLESS:-<unset>}

== Sessions ==
xhs_state.json: $( [[ -f "$SESSIONS_DIR/xhs_state.json" ]] && echo "PRESENT" || echo "MISSING" )
dy_state.json: $( [[ -f "$SESSIONS_DIR/dy_state.json" ]] && echo "PRESENT" || echo "MISSING" )
MediaCrawler sessions aligned: $( [[ -L "$MC_SESSIONS_DIR" || -d "$MC_SESSIONS_DIR" ]] && echo "YES" || echo "NO" )

== Runtime ==
runtime.server.yaml: $( [[ -f "$RUNTIME_CONFIG_PATH" ]] && echo "$RUNTIME_CONFIG_PATH" || echo "MISSING" )

== LLM Keys ==
$(llm_key_status "OPENAI_BASE_URL")
$(llm_key_status "OPENAI_API_KEY")
$(llm_key_status "OPENAI_MODEL")
$(llm_key_status "DEEPSEEK_API_KEY")
$(llm_key_status "DEEPSEEK_MODEL")
$(llm_key_status "ANTHROPIC_API_KEY")
$(llm_key_status "OPENROUTER_API_KEY")
$(llm_key_status "OPENROUTER_IMAGE_MODEL")
$(llm_key_status "DASHSCOPE_API_KEY")
EOF
}

post_install_smoke() {
  log "运行部署后 smoke 检查"
  "$APP_VENV/bin/python" -m compileall apps/intel_hub apps/growth_lab >/dev/null
  if [[ "$SKIP_TRENDRADAR" -eq 0 ]]; then
    "$TR_VENV/bin/python" -m trendradar --help >/dev/null
  fi
  if [[ "$SKIP_MEDIACRAWLER" -eq 0 ]]; then
    "$MC_VENV/bin/python" "$MC_ROOT/legacy_intel_hub_runner.py" --help >/dev/null
  fi
}

import_data_bundle_if_provided() {
  if [[ -z "$DATA_BUNDLE" ]]; then
    return 0
  fi
  local bundle_path="$DATA_BUNDLE"
  if [[ ! -f "$bundle_path" ]]; then
    warn "--bundle 指定的文件不存在，跳过导入: $bundle_path"
    return 0
  fi
  local bootstrap_script="$REPO_ROOT/scripts/bootstrap_data.sh"
  if [[ ! -x "$bootstrap_script" ]]; then
    warn "缺少 scripts/bootstrap_data.sh，跳过 --bundle 导入"
    return 0
  fi
  log "导入数据快照: $bundle_path (mode=$DATA_BUNDLE_MODE)"
  PYTHON_BIN="$APP_VENV/bin/python" \
    bash "$bootstrap_script" \
      --bundle "$bundle_path" \
      --install-dir "$REPO_ROOT" \
      --mode "$DATA_BUNDLE_MODE" \
      --service "$APP_SERVICE_NAME" \
      --restart-service \
    || warn "数据快照导入失败，请人工排查（详见上方 [WARN]/[FAIL] 日志）"
}

summary() {
  cat <<EOF

${C_GREEN}===== Ubuntu 部署完成 =====${C_RESET}
主站服务:
  systemd: $APP_SERVICE_NAME
  runtime: $RUNTIME_CONFIG_PATH
  listen : http://$HOST:$PORT

第三方:
  TrendRadar: $( [[ "$SKIP_TRENDRADAR" -eq 1 ]] && echo "skipped" || echo "$TR_ROOT @ $TRENDRADAR_PIN_COMMIT" )
  MediaCrawler: $( [[ "$SKIP_MEDIACRAWLER" -eq 1 ]] && echo "skipped" || echo "$MC_ROOT" )

登录态:
  sessions dir: $SESSIONS_DIR
  xhs imported: $( [[ -f "$SESSIONS_DIR/xhs_state.json" ]] && echo "yes" || echo "no" )
  dy imported : $( [[ -f "$SESSIONS_DIR/dy_state.json" ]] && echo "yes" || echo "no" )

数据快照:
  bundle      : $( [[ -n "$DATA_BUNDLE" ]] && echo "$DATA_BUNDLE (mode=$DATA_BUNDLE_MODE)" || echo "<未提供，可后续 bash scripts/bootstrap_data.sh --bundle ...>" )

能力降级提醒:
  OPENAI_API_KEY 缺失会影响主 LLM 链路
  DEEPSEEK / ANTHROPIC 缺失会失去对应 provider fallback
  OPENROUTER / DASHSCOPE 缺失会影响图像与视觉链路
  未导入登录态时，主站与 TrendRadar 可运行，但采集会提示先导入登录态

常用命令:
  bash install.sh --doctor
  sudo systemctl status $APP_SERVICE_NAME
  sudo journalctl -u $APP_SERVICE_NAME -f
EOF
}

main() {
  require_repo_root
  if [[ "$DOCTOR_ONLY" -eq 1 ]]; then
    run_doctor
    exit 0
  fi
  check_ubuntu
  apt_install
  ensure_python_binaries
  ensure_runtime_dirs
  install_root_venv
  ensure_trendradar_repo
  install_trendradar_venv
  install_mediacrawler_venv
  render_runtime_server_yaml
  ensure_env_template
  import_sessions_if_needed
  align_mediacrawler_sessions_dir
  install_systemd_units
  post_install_smoke
  import_data_bundle_if_provided
  run_doctor
  summary
}

main "$@"
