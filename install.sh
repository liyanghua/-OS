#!/usr/bin/env bash
# =============================================================================
# OntologyBrain / AI-native 经营操作 OS —— 一键部署脚本
# -----------------------------------------------------------------------------
# 使用方法（在目标服务器 root 或具备 sudo 权限的用户下执行）：
#
#   # 方式 A：已经 git clone 好代码
#   bash install.sh
#
#   # 方式 B：直接远程拉起
#   curl -fsSL https://<your-host>/install.sh | bash -s -- \
#        --repo git@github.com:<you>/<repo>.git --branch main
#
# 可用参数：
#   --repo      <git url>     仓库地址（未在当前目录时使用）
#   --branch    <branch>      分支，默认 main
#   --dir       <path>        安装目录，默认 /opt/ontology-os
#   --port      <port>        监听端口，默认 8000
#   --host      <host>        监听地址，默认 0.0.0.0
#   --python    <bin>         指定 python 可执行文件，默认自动探测 (>=3.11)
#   --no-service              不安装 systemd 服务，仅准备环境
#   --no-submodules           跳过 git submodule 拉取
#   --skip-system-deps        跳过 apt/yum 系统依赖安装
#   --env-file  <path>        使用现成 .env 文件（拷贝到安装目录）
# =============================================================================
set -Eeuo pipefail

# ---------------------------- 默认参数 ---------------------------------------
REPO_URL=""
BRANCH="main"
INSTALL_DIR="${INSTALL_DIR:-/opt/ontology-os}"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
PYTHON_BIN=""
INSTALL_SERVICE=1
PULL_SUBMODULES=1
SKIP_SYSTEM_DEPS=0
CUSTOM_ENV_FILE=""
SERVICE_NAME="ontology-os"
APP_MODULE="apps.intel_hub.api.app:create_app"

# ---------------------------- 彩色日志 ---------------------------------------
if [[ -t 1 ]]; then
  C_RED="\033[31m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_RESET="\033[0m"
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_RESET=""
fi
log()   { echo -e "${C_BLUE}[INFO]${C_RESET} $*"; }
ok()    { echo -e "${C_GREEN}[ OK ]${C_RESET} $*"; }
warn()  { echo -e "${C_YELLOW}[WARN]${C_RESET} $*"; }
err()   { echo -e "${C_RED}[FAIL]${C_RESET} $*" >&2; }
die()   { err "$*"; exit 1; }

trap 'err "部署失败，行号: $LINENO"' ERR

# ---------------------------- 参数解析 ---------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)             REPO_URL="$2"; shift 2;;
    --branch)           BRANCH="$2"; shift 2;;
    --dir)              INSTALL_DIR="$2"; shift 2;;
    --port)             PORT="$2"; shift 2;;
    --host)             HOST="$2"; shift 2;;
    --python)           PYTHON_BIN="$2"; shift 2;;
    --no-service)       INSTALL_SERVICE=0; shift;;
    --no-submodules)    PULL_SUBMODULES=0; shift;;
    --skip-system-deps) SKIP_SYSTEM_DEPS=1; shift;;
    --env-file)         CUSTOM_ENV_FILE="$2"; shift 2;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0;;
    *) die "未知参数: $1";;
  esac
done

# ---------------------------- sudo 包装 --------------------------------------
if [[ $EUID -eq 0 ]]; then
  SUDO=""
else
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    die "需要 root 权限或已安装 sudo"
  fi
fi

# ---------------------------- 1. 系统依赖 ------------------------------------
detect_os() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_FAMILY="${ID_LIKE:-$ID}"
    OS_ID="$ID"
  else
    OS_FAMILY="unknown"; OS_ID="unknown"
  fi
}

install_system_deps() {
  if [[ "$SKIP_SYSTEM_DEPS" -eq 1 ]]; then
    warn "跳过系统依赖安装 (--skip-system-deps)"; return
  fi
  detect_os
  log "检测到系统: $OS_ID ($OS_FAMILY)"

  case "$OS_FAMILY $OS_ID" in
    *debian*|*ubuntu*)
      $SUDO apt-get update -y
      $SUDO apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential \
        python3 python3-venv python3-dev python3-pip \
        pkg-config libssl-dev
      if ! command -v python3.11 >/dev/null 2>&1 && ! python3 -c 'import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)'; then
        warn "系统 python3 版本低于 3.11，尝试安装 python3.11"
        $SUDO apt-get install -y software-properties-common || true
        $SUDO add-apt-repository -y ppa:deepin-opt/python3.11 2>/dev/null || \
          $SUDO add-apt-repository -y ppa:deadsnakes/ppa || true
        $SUDO apt-get update -y || true
        $SUDO apt-get install -y python3.11 python3.11-venv python3.11-dev || \
          warn "自动安装 python3.11 失败，请手动安装后重试"
      fi
      ;;
    *rhel*|*centos*|*fedora*|*rocky*|*almalinux*)
      if command -v dnf >/dev/null 2>&1; then PM="dnf"; else PM="yum"; fi
      $SUDO $PM install -y ca-certificates curl git gcc gcc-c++ make \
        python3 python3-devel python3-pip openssl-devel || true
      $SUDO $PM install -y python3.11 python3.11-devel || \
        warn "未能安装 python3.11，继续使用系统默认 python3"
      ;;
    *)
      warn "未识别的发行版，跳过系统依赖安装。请自行准备: git, python>=3.11, pip, venv, build tools"
      ;;
  esac
  ok "系统依赖就绪"
}

# ---------------------------- 2. 选择 Python ---------------------------------
pick_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    command -v "$PYTHON_BIN" >/dev/null || die "指定的 python 不存在: $PYTHON_BIN"
  else
    for c in python3.12 python3.11 python3; do
      if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)'; then
          PYTHON_BIN="$c"; break
        fi
      fi
    done
  fi
  [[ -z "$PYTHON_BIN" ]] && die "未找到 Python>=3.11，请手动安装后再运行"
  ok "使用 Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"
}

# ---------------------------- 3. 获取代码 ------------------------------------
fetch_code() {
  if [[ -f "pyproject.toml" && -d "apps/intel_hub" ]]; then
    log "当前目录已是项目根目录，使用本地代码"
    INSTALL_DIR="$(pwd)"
    return
  fi

  [[ -z "$REPO_URL" ]] && die "当前目录不是项目根，且未通过 --repo 指定仓库地址"

  $SUDO mkdir -p "$(dirname "$INSTALL_DIR")"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "更新已存在仓库: $INSTALL_DIR"
    $SUDO git -C "$INSTALL_DIR" fetch --all --prune
    $SUDO git -C "$INSTALL_DIR" checkout "$BRANCH"
    $SUDO git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  else
    log "克隆仓库: $REPO_URL -> $INSTALL_DIR"
    $SUDO git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi

  if [[ "$PULL_SUBMODULES" -eq 1 ]]; then
    log "拉取 git submodules"
    $SUDO git -C "$INSTALL_DIR" submodule update --init --recursive || \
      warn "部分 submodule 拉取失败，可稍后手动执行 git submodule update"
  fi

  if [[ $EUID -ne 0 ]]; then
    $SUDO chown -R "$USER":"$(id -gn)" "$INSTALL_DIR" 2>/dev/null || true
  fi
  ok "代码已就绪: $INSTALL_DIR"
}

# ---------------------------- 4. Python 环境 & 依赖 --------------------------
setup_venv() {
  cd "$INSTALL_DIR"
  if [[ ! -d ".venv" ]]; then
    log "创建虚拟环境 .venv"
    "$PYTHON_BIN" -m venv .venv
  else
    log "复用已有虚拟环境 .venv"
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip wheel setuptools

  log "安装项目依赖 (pyproject.toml)"
  # 可选的 LLM / browser 依赖默认全装；如需精简可改为 pip install -e .
  pip install -e ".[llm-all]" || pip install -e .

  # Next.js 前端（可选：仅在存在 package.json 且安装了 node 时构建）
  if [[ -f "package.json" ]] && command -v npm >/dev/null 2>&1; then
    log "检测到 Next.js 前端，执行 npm install && build"
    npm install --no-audit --no-fund || warn "npm install 失败，前端部分将跳过"
    npm run build || warn "next build 失败，前端部分将跳过"
  fi
  ok "Python 环境与依赖安装完成"
}

# ---------------------------- 5. 环境变量 ------------------------------------
setup_env() {
  cd "$INSTALL_DIR"
  if [[ -n "$CUSTOM_ENV_FILE" ]]; then
    [[ -f "$CUSTOM_ENV_FILE" ]] || die "--env-file 指定的文件不存在: $CUSTOM_ENV_FILE"
    cp "$CUSTOM_ENV_FILE" .env
    ok "已使用自定义 .env: $CUSTOM_ENV_FILE"
    return
  fi
  if [[ -f ".env" ]]; then
    ok ".env 已存在，保留现有配置"
    return
  fi
  log "生成 .env 模板（请部署后填入真实 key）"
  cat > .env <<'EOF'
# ===== LLM 文本 =====
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-REPLACE_ME
OPENAI_MODEL=gpt-4o-mini

# ===== OpenRouter 图像 =====
OPENROUTER_API_KEY=sk-or-REPLACE_ME
OPENROUTER_IMAGE_MODEL=google/gemini-2.5-flash-image
OPENROUTER_IMAGE_MODEL_FALLBACKS=google/gemini-2.5-flash-image,bytedance-seed/seedream-4.5

# ===== DashScope 图像编辑 =====
DASHSCOPE_API_KEY=sk-REPLACE_ME
DASHSCOPE_IMAGE_EDIT_MODEL=qwen-image-edit
EOF
  chmod 600 .env
  warn ".env 已生成模板，请编辑 $INSTALL_DIR/.env 后再启动服务"
}

# ---------------------------- 6. systemd 服务 --------------------------------
install_systemd() {
  if [[ "$INSTALL_SERVICE" -eq 0 ]]; then
    warn "跳过 systemd 服务安装 (--no-service)"; return
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    warn "系统无 systemd，跳过服务注册"; return
  fi

  local run_user="${SUDO_USER:-$USER}"
  [[ "$run_user" == "root" ]] && run_user="root"

  local unit_file="/etc/systemd/system/${SERVICE_NAME}.service"
  log "写入 systemd 服务: $unit_file (运行用户: $run_user)"

  $SUDO tee "$unit_file" >/dev/null <<EOF
[Unit]
Description=Ontology AI-native Commerce Operating System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${run_user}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/.venv/bin/uvicorn ${APP_MODULE} --factory --host ${HOST} --port ${PORT}
Restart=on-failure
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30
# 日志
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  $SUDO systemctl daemon-reload
  $SUDO systemctl enable "$SERVICE_NAME"
  $SUDO systemctl restart "$SERVICE_NAME"
  sleep 2
  if $SUDO systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "服务已启动: systemctl status $SERVICE_NAME"
  else
    warn "服务未处于 active 状态，请检查: journalctl -u $SERVICE_NAME -n 200 --no-pager"
  fi
}

# ---------------------------- 7. 防火墙提示 ---------------------------------
firewall_hint() {
  if command -v ufw >/dev/null 2>&1; then
    log "如启用了 ufw，可执行: sudo ufw allow ${PORT}/tcp"
  elif command -v firewall-cmd >/dev/null 2>&1; then
    log "如启用了 firewalld，可执行: sudo firewall-cmd --permanent --add-port=${PORT}/tcp && sudo firewall-cmd --reload"
  fi
}

# ---------------------------- 8. 汇总输出 -----------------------------------
summary() {
  cat <<EOF

${C_GREEN}===== 部署完成 =====${C_RESET}
  安装目录    : ${INSTALL_DIR}
  Python      : ${PYTHON_BIN}
  监听地址    : http://${HOST}:${PORT}
  服务名      : ${SERVICE_NAME} $( [[ $INSTALL_SERVICE -eq 1 ]] && echo "(systemd 已启用)" || echo "(未安装 systemd 服务)" )
  配置文件    : ${INSTALL_DIR}/.env

常用命令：
  启动/停止 : sudo systemctl start|stop|restart ${SERVICE_NAME}
  查看日志 : sudo journalctl -u ${SERVICE_NAME} -f
  手动启动 : cd ${INSTALL_DIR} && source .venv/bin/activate \\
             && uvicorn ${APP_MODULE} --factory --host ${HOST} --port ${PORT}

EOF
}

# ============================ 主流程 =========================================
main() {
  log "开始部署 AI-native 经营操作 OS"
  install_system_deps
  pick_python
  fetch_code
  setup_venv
  setup_env
  install_systemd
  firewall_hint
  summary
}

main "$@"
