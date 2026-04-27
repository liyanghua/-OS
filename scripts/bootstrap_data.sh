#!/usr/bin/env bash
# =============================================================================
# bootstrap_data.sh — 客户侧服务器一键引入由 export_dataset.sh 产生的数据快照
# -----------------------------------------------------------------------------
# 用法：
#   bash scripts/bootstrap_data.sh --bundle /tmp/dataset_xxx.tar.gz
#   bash scripts/bootstrap_data.sh --bundle /tmp/dataset.tar.gz --mode safe --restart-service
#   bash scripts/bootstrap_data.sh --rebuild   # 不导入 sqlite，从 raw jsonl 重建
#
# 参数：
#   --bundle <tar.gz>          快照压缩包路径
#   --install-dir <path>       目标根目录，默认脚本所在仓库根
#   --mode safe|overwrite      已存在文件的处理策略，默认 safe（备份原文件后写入）
#   --service <name>           systemd 服务名，默认 ontology-os
#   --restart-service          导入完成后 systemctl restart
#   --rebuild                  不导入快照；尝试调 xhs_opportunity_pipeline 从 raw jsonl 重建
#   --no-sync                  跳过 sync_cards_from_json
#   --no-validate              跳过 sqlite 表校验
#   -h|--help                  打印此帮助
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------- 默认参数 ---------------------------------------
BUNDLE=""
INSTALL_DIR="$REPO_ROOT"
MODE="safe"               # safe | overwrite
SERVICE_NAME="ontology-os"
RESTART_SERVICE=0
REBUILD=0
DO_SYNC=1
DO_VALIDATE=1
SERVICE_STOPPED=0

# ---------------------------- 日志 -------------------------------------------
if [[ -t 1 ]]; then
  C_GREEN="\033[32m"; C_YELLOW="\033[33m"; C_BLUE="\033[34m"; C_RED="\033[31m"; C_RESET="\033[0m"
else
  C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_RED=""; C_RESET=""
fi
log()   { echo -e "${C_BLUE}[INFO]${C_RESET} $*"; }
ok()    { echo -e "${C_GREEN}[ OK ]${C_RESET} $*"; }
warn()  { echo -e "${C_YELLOW}[WARN]${C_RESET} $*"; }
err()   { echo -e "${C_RED}[FAIL]${C_RESET} $*" >&2; }
die()   { err "$*"; exit 1; }
trap 'err "数据引入失败，行号: $LINENO"' ERR

# ---------------------------- 参数解析 ---------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle)            BUNDLE="$2"; shift 2;;
    --install-dir)       INSTALL_DIR="$2"; shift 2;;
    --mode)              MODE="$2"; shift 2;;
    --service)           SERVICE_NAME="$2"; shift 2;;
    --restart-service)   RESTART_SERVICE=1; shift;;
    --rebuild)           REBUILD=1; shift;;
    --no-sync)           DO_SYNC=0; shift;;
    --no-validate)       DO_VALIDATE=0; shift;;
    -h|--help)
      sed -n '2,22p' "$0"; exit 0;;
    *) die "未知参数: $1";;
  esac
done

case "$MODE" in
  safe|overwrite) ;;
  *) die "--mode 仅支持 safe|overwrite，当前: $MODE";;
esac

[[ -d "$INSTALL_DIR" ]] || die "INSTALL_DIR 不存在: $INSTALL_DIR"
[[ -f "$INSTALL_DIR/pyproject.toml" ]] || die "INSTALL_DIR 不像仓库根（缺 pyproject.toml）: $INSTALL_DIR"

# 选择 Python 解释器
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$INSTALL_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi
log "使用 Python: $PYTHON_BIN"

# ---------------------------- sudo 包装 --------------------------------------
if [[ $EUID -eq 0 ]]; then
  SUDO=""
else
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    SUDO=""
  fi
fi

# ---------------------------- helpers ----------------------------------------
backup_path() {
  local path="$1"
  local ts="$(date +%Y%m%d_%H%M%S)"
  if [[ -e "$path" ]]; then
    mv "$path" "${path}.bak.${ts}"
    warn "已备份 $path -> ${path}.bak.${ts}"
  fi
}

ensure_dir() {
  mkdir -p "$1"
}

runtime_state_paths() {
  cat <<'EOF'
data/alerts.json
data/job_queue.json
data/crawl_status.json
data/crawl_status_xhs.json
data/pipeline_status_xhs.json
EOF
}

# ---------------------------- 1. 解包流程（快照） ----------------------------
# bundle 解析：支持
#   - 单个 tar.gz 文件
#   - 目录（含 dataset.tar.gz / dataset.tar.gz.part_* / dataset.tar.gz.sha256）
#   - 任意一个 dataset.tar.gz.part_aa（同目录内自动找全部 part_*）
resolve_bundle_to_tarball() {
  local input="$BUNDLE"
  [[ -n "$input" ]] || die "--bundle 必填"

  local search_dir tarball
  if [[ -d "$input" ]]; then
    search_dir="$input"
  elif [[ -f "$input" ]]; then
    if [[ "$input" == *.part_* ]]; then
      search_dir="$(dirname "$input")"
    else
      # 直接是 tar.gz
      RESOLVED_BUNDLE="$input"
      return 0
    fi
  else
    die "bundle 不存在: $input"
  fi

  # 优先用现成的 dataset.tar.gz
  if [[ -f "$search_dir/dataset.tar.gz" ]]; then
    RESOLVED_BUNDLE="$search_dir/dataset.tar.gz"
    log "复用已存在的 $RESOLVED_BUNDLE"
    return 0
  fi

  # 重组分片
  local parts=()
  while IFS= read -r f; do parts+=("$f"); done < <(find "$search_dir" -maxdepth 1 -type f -name 'dataset.tar.gz.part_*' | sort)
  [[ ${#parts[@]} -gt 0 ]] || die "在 $search_dir 中未找到 dataset.tar.gz 也未找到 dataset.tar.gz.part_* 切片"

  tarball="$search_dir/dataset.tar.gz"
  log "重组 ${#parts[@]} 个分片 -> $tarball"
  cat "${parts[@]}" > "$tarball"

  # 校验 SHA256（如果有 .sha256 文件）
  local sha_file="$search_dir/dataset.tar.gz.sha256"
  if [[ -f "$sha_file" ]]; then
    local expected actual
    expected="$(awk '{print $1}' "$sha_file" | head -1)"
    if command -v shasum >/dev/null 2>&1; then
      actual="$(shasum -a 256 "$tarball" | awk '{print $1}')"
    elif command -v sha256sum >/dev/null 2>&1; then
      actual="$(sha256sum "$tarball" | awk '{print $1}')"
    else
      warn "未找到 shasum/sha256sum，跳过校验"
      actual=""
    fi
    if [[ -n "$actual" ]]; then
      if [[ "$expected" == "$actual" ]]; then
        ok "SHA256 校验通过 ($expected)"
      else
        die "SHA256 不匹配!  expected=$expected  actual=$actual"
      fi
    fi
  else
    warn "未找到 dataset.tar.gz.sha256，跳过完整性校验"
  fi
  RESOLVED_BUNDLE="$tarball"
}

extract_bundle() {
  resolve_bundle_to_tarball
  [[ -f "$RESOLVED_BUNDLE" ]] || die "无法解析 bundle: $BUNDLE"

  STAGING="$(mktemp -d -t ontoboot.XXXXXX)"
  trap 'rm -rf "$STAGING"' EXIT
  log "解包 $RESOLVED_BUNDLE 到临时目录 $STAGING"
  tar -xzf "$RESOLVED_BUNDLE" -C "$STAGING"

  # manifest 校验（warn 不阻断）
  if [[ -f "$STAGING/manifest.json" ]]; then
    log "manifest:"
    grep -E '"(exported_at|git_commit|git_branch|profile|total_size_kb)"' \
      "$STAGING/manifest.json" | sed 's/^/    /'
    local local_commit
    local_commit="$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || echo)"
    local bundle_commit
    bundle_commit="$(grep -E '"git_commit"' "$STAGING/manifest.json" | head -1 | sed -E 's/.*"git_commit"\s*:\s*"([^"]*)".*/\1/')"
    if [[ -n "$local_commit" && -n "$bundle_commit" && "$local_commit" != "$bundle_commit" ]]; then
      warn "git_commit 不一致: 本地=$local_commit  bundle=$bundle_commit"
    fi
  else
    warn "bundle 缺少 manifest.json"
  fi

  # 实际数据要么落 $STAGING/data，要么 $STAGING/<root>/data。判断后取 SRC_ROOT。
  if [[ -d "$STAGING/data" ]]; then
    SRC_ROOT="$STAGING"
  else
    SRC_ROOT="$(find "$STAGING" -maxdepth 2 -type d -name data | head -1 | xargs dirname 2>/dev/null || echo "$STAGING")"
  fi
  log "源数据根: $SRC_ROOT"
}

apply_payload() {
  local rel="$1"
  local src="$SRC_ROOT/$rel"
  local dst="$INSTALL_DIR/$rel"
  [[ -e "$src" ]] || return 0

  ensure_dir "$(dirname "$dst")"
  if [[ "$MODE" == "safe" ]]; then
    backup_path "$dst"
  fi
  if [[ -d "$src" ]]; then
    if command -v rsync >/dev/null 2>&1; then
      rsync -a "$src/" "$dst/"
    else
      cp -R "$src/." "$dst/"
    fi
  else
    cp "$src" "$dst"
  fi
  ok "导入: $rel"
}

import_snapshot() {
  log "开始导入快照"

  # 1. 关键 SQLite 文件
  while IFS= read -r f; do
    rel="${f#$SRC_ROOT/}"
    apply_payload "$rel"
  done < <(find "$SRC_ROOT/data" -maxdepth 1 -type f \( -name "*.sqlite" -o -name "*.db" \) 2>/dev/null)

  # 2. 关键 JSON（仅业务产物，不导入运行态 queue/status/alerts）
  for rel in \
    data/opportunity_cards.json \
    data/pipeline_details.json
  do
    apply_payload "$rel"
  done

  # 3. 子目录批量
  for rel in \
    data/output \
    data/fixtures \
    data/raw \
    data/raw_lake \
    data/generated_images \
    data/generated_videos \
    data/source_images \
    data/exports \
    data/template_extraction \
    data/sessions
  do
    apply_payload "$rel"
  done

  # 4. MediaCrawler jsonl
  for plat in xhs douyin; do
    apply_payload "third_party/MediaCrawler/data/${plat}/jsonl"
  done

  # 5. 明确清理运行态文件，避免旧机器告警 / 队列 / 状态复活。
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    rm -f "$INSTALL_DIR/$rel"
  done < <(runtime_state_paths)

  # 6. 权限修正
  if [[ -n "${SUDO_USER:-}" && $EUID -eq 0 ]]; then
    chown -R "$SUDO_USER":"$(id -gn "$SUDO_USER" 2>/dev/null || echo "$SUDO_USER")" "$INSTALL_DIR/data" 2>/dev/null || true
  fi
  ok "快照导入完成"
}

# ---------------------------- 2. 重建模式 ------------------------------------
rebuild_from_raw() {
  log "rebuild 模式：从 MediaCrawler jsonl 重新跑 pipeline"
  local jsonl_dir="$INSTALL_DIR/third_party/MediaCrawler/data/xhs/jsonl"
  if [[ ! -d "$jsonl_dir" ]]; then
    if [[ -d "$INSTALL_DIR/data/fixtures/mediacrawler_output/xhs/jsonl" ]]; then
      jsonl_dir="$INSTALL_DIR/data/fixtures/mediacrawler_output/xhs/jsonl"
      warn "未找到 MediaCrawler jsonl，回退 fixtures: $jsonl_dir"
    else
      die "rebuild 模式但未找到 jsonl 目录"
    fi
  fi
  cd "$INSTALL_DIR"
  "$PYTHON_BIN" -m apps.intel_hub.workflow.xhs_opportunity_pipeline \
    --jsonl-dir "$jsonl_dir" \
    --output-dir "$INSTALL_DIR/data/output/xhs_opportunities" \
    || warn "xhs_opportunity_pipeline 退出非零，请检查 LLM key 与日志"
  "$PYTHON_BIN" -c "from apps.intel_hub.workflow.refresh_pipeline import run_pipeline; run_pipeline()" \
    || warn "refresh_pipeline.run_pipeline 退出非零"
}

# ---------------------------- 3. 入库 sync + 校验 ----------------------------
post_import() {
  cd "$INSTALL_DIR"

  if [[ "$DO_SYNC" -eq 1 ]]; then
    log "sync_cards_from_json -> xhs_review.sqlite"
    "$PYTHON_BIN" -m apps.intel_hub.scripts.bootstrap_data sync-cards
  fi

  if [[ "$DO_VALIDATE" -eq 1 ]]; then
    log "校验 SQLite 连通性 + 关键表"
    "$PYTHON_BIN" -m apps.intel_hub.scripts.bootstrap_data validate
  fi

  log "汇总当前数据规模"
  "$PYTHON_BIN" -m apps.intel_hub.scripts.bootstrap_data summary || true
}

# ---------------------------- 4. systemd restart -----------------------------
maybe_restart_service() {
  [[ "$RESTART_SERVICE" -eq 1 ]] || return 0
  if ! command -v systemctl >/dev/null 2>&1; then
    warn "无 systemctl，跳过 service 重启"
    return 0
  fi
  if ! $SUDO systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\.service"; then
    warn "未找到 systemd 服务: $SERVICE_NAME，跳过"
    return 0
  fi
  log "重启 systemd 服务: $SERVICE_NAME"
  $SUDO systemctl restart "$SERVICE_NAME" || warn "systemctl restart 失败"
  sleep 2
  $SUDO systemctl is-active --quiet "$SERVICE_NAME" \
    && ok "服务已 active" \
    || warn "服务未 active，可查 journalctl -u $SERVICE_NAME -n 200 --no-pager"
}

stop_service_before_import_if_needed() {
  [[ "$RESTART_SERVICE" -eq 1 ]] || return 0
  if ! command -v systemctl >/dev/null 2>&1; then
    return 0
  fi
  if ! $SUDO systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}\.service"; then
    return 0
  fi
  log "导入前停止 systemd 服务: $SERVICE_NAME"
  $SUDO systemctl stop "$SERVICE_NAME"
  SERVICE_STOPPED=1
}

# ---------------------------- 主流程 -----------------------------------------
main() {
  log "客户侧数据引入：install_dir=$INSTALL_DIR mode=$MODE rebuild=$REBUILD"
  stop_service_before_import_if_needed

  if [[ "$REBUILD" -eq 1 ]]; then
    if [[ -n "$BUNDLE" ]]; then
      log "rebuild 模式：仍解包以获取 raw jsonl"
      extract_bundle
      # 仅导入 raw / fixtures / mediacrawler，不导入 sqlite/json
      MODE_BACKUP="$MODE"
      MODE="$MODE"
      for rel in data/raw data/raw_lake data/fixtures \
                 third_party/MediaCrawler/data/xhs/jsonl \
                 third_party/MediaCrawler/data/douyin/jsonl; do
        apply_payload "$rel"
      done
      MODE="$MODE_BACKUP"
    fi
    rebuild_from_raw
  else
    extract_bundle
    import_snapshot
  fi

  post_import
  maybe_restart_service

  cat <<EOF

${C_GREEN}===== 数据引入完成 =====${C_RESET}
  install_dir : ${INSTALL_DIR}
  mode        : ${MODE}$( [[ $REBUILD -eq 1 ]] && echo " (rebuild)" )
  bundle      : ${BUNDLE:-<none>}
  service     : ${SERVICE_NAME}$( [[ $RESTART_SERVICE -eq 1 ]] && echo " (restarted)" )

下一步建议：
  1) curl -I http://127.0.0.1:8000/         # 验证主站可达
  2) 浏览器访问 /xhs-opportunities          # 应显示 import 后的机会卡列表
  3) 浏览器访问 /planning/<opportunity_id>  # 应显示对应内容策划工作台

EOF
}

main "$@"
