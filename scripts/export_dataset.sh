#!/usr/bin/env bash
# =============================================================================
# export_dataset.sh — 把本机已采的全套运行时数据打包成 tar.gz
# -----------------------------------------------------------------------------
# 用途：在本机 Mac 上一键导出 data/ + MediaCrawler jsonl + manifest.json，
# 供客户侧服务器通过 scripts/bootstrap_data.sh 引入，免浏览器采集即可起服务。
#
# 默认包含（"全量"档）：
#   - data/                       业务 sqlite + output + 资源目录（sqlite 走 .backup 在线快照）
#   - data/fixtures/              覆盖 fallback 路径
#   - third_party/MediaCrawler/data/<platform>/jsonl/   MediaCrawler 原始 jsonl
#   - manifest.json               导出元数据（git commit、行数、文件大小）
#
# 默认排除：
#   - data/sessions/*.session     避免 cookie/登录态外泄
#   - data/job_queue.json / alerts.json / crawl_status*.json 等运行态文件
#   - browser_data/, *.log, __pycache__
#
# 用法：
#   bash scripts/export_dataset.sh                       # 输出到 dist/dataset_<date>.tar.gz
#   bash scripts/export_dataset.sh --out /tmp/ds.tar.gz  # 指定输出路径
#   bash scripts/export_dataset.sh --lite                # 仅 L2+L3 必要数据
#   bash scripts/export_dataset.sh --include-sessions    # 同时导出 data/sessions（会带 cookie）
# =============================================================================
set -Eeuo pipefail

# ---------------------------- 路径 -------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------- 默认参数 ---------------------------------------
TS="$(date +%Y%m%d_%H%M%S)"
OUT_PATH="$REPO_ROOT/dist/dataset_${TS}.tar.gz"
LITE=0
INCLUDE_SESSIONS=0
INCLUDE_RAW=1            # 是否打包 data/raw, data/raw_lake
INCLUDE_FIXTURES=1
INCLUDE_MEDIACRAWLER=1

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

# ---------------------------- 参数解析 ---------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)               OUT_PATH="$2"; shift 2;;
    --lite)              LITE=1; INCLUDE_RAW=0; INCLUDE_FIXTURES=0; shift;;
    --include-sessions)  INCLUDE_SESSIONS=1; shift;;
    --no-mediacrawler)   INCLUDE_MEDIACRAWLER=0; shift;;
    --no-fixtures)       INCLUDE_FIXTURES=0; shift;;
    --no-raw)            INCLUDE_RAW=0; shift;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0;;
    *) die "未知参数: $1";;
  esac
done

# ---------------------------- 前置检查 ---------------------------------------
command -v tar >/dev/null   || die "缺少 tar"
command -v gzip >/dev/null  || die "缺少 gzip"
SQLITE_BIN="$(command -v sqlite3 || true)"
[[ -z "$SQLITE_BIN" ]] && warn "sqlite3 未找到，将退化为 cp（运行中数据库可能拷到不一致快照）"

[[ -d "data" ]] || die "未找到 $REPO_ROOT/data，请确认在仓库根执行"

mkdir -p "$(dirname "$OUT_PATH")"
STAGING="$(mktemp -d -t ontoexport.XXXXXX)"
trap 'rm -rf "$STAGING"' EXIT

log "暂存目录: $STAGING"
log "输出路径: $OUT_PATH"
[[ "$LITE" -eq 1 ]] && warn "lite 模式：跳过 raw/fixtures，仅保留 sqlite + opportunity_cards JSON"

# ---------------------------- 1. SQLite 在线快照 ----------------------------
mkdir -p "$STAGING/data"
SQLITE_FILES=()
while IFS= read -r f; do SQLITE_FILES+=("$f"); done < <(find data -maxdepth 2 -type f \( -name "*.sqlite" -o -name "*.db" \) 2>/dev/null | sort)

DB_ROWS_JSON="$STAGING/_db_rows.tmp.json"
echo "{}" > "$DB_ROWS_JSON"

for db in "${SQLITE_FILES[@]}"; do
  rel="${db#data/}"
  dest="$STAGING/data/$rel"
  mkdir -p "$(dirname "$dest")"
  if [[ -n "$SQLITE_BIN" ]]; then
    if "$SQLITE_BIN" "$db" ".backup '$dest'" 2>/dev/null; then
      log "snapshot: $db -> $dest"
    else
      warn "sqlite3 .backup 失败，回退 cp: $db"
      cp "$db" "$dest"
    fi
  else
    cp "$db" "$dest"
  fi
  size_h="$(du -h "$dest" 2>/dev/null | awk '{print $1}')"
  log "  size=${size_h}"
done

# ---------------------------- 2. JSON / output 关键文件 ---------------------
JSON_LIST=(
  "data/opportunity_cards.json"
  "data/pipeline_details.json"
)
for f in "${JSON_LIST[@]}"; do
  if [[ -f "$f" ]]; then
    mkdir -p "$STAGING/$(dirname "$f")"
    cp "$f" "$STAGING/$f"
    log "copy: $f"
  fi
done

# data/output/ 整个拷过去（机会卡 JSON + lens_bundles + runs）
if [[ -d "data/output" ]]; then
  mkdir -p "$STAGING/data/output"
  rsync -a --delete \
    --exclude '*.tmp' --exclude '*.swp' \
    "data/output/" "$STAGING/data/output/" 2>/dev/null || cp -R data/output/. "$STAGING/data/output/"
  ok "copy: data/output/"
fi

# generated_images / generated_videos / source_images（可选大体积）
if [[ "$LITE" -eq 0 ]]; then
  for d in data/generated_images data/generated_videos data/source_images data/exports data/template_extraction; do
    if [[ -d "$d" ]]; then
      mkdir -p "$STAGING/$d"
      rsync -a "$d/" "$STAGING/$d/" 2>/dev/null || cp -R "$d/." "$STAGING/$d/"
      log "copy: $d/"
    fi
  done
fi

# ---------------------------- 3. raw / sessions / fixtures ------------------
if [[ "$INCLUDE_RAW" -eq 1 ]]; then
  for d in data/raw data/raw_lake; do
    if [[ -d "$d" ]]; then
      mkdir -p "$STAGING/$d"
      rsync -a "$d/" "$STAGING/$d/" 2>/dev/null || cp -R "$d/." "$STAGING/$d/"
      ok "copy: $d/"
    fi
  done
fi

if [[ "$INCLUDE_FIXTURES" -eq 1 && -d "data/fixtures" ]]; then
  mkdir -p "$STAGING/data/fixtures"
  rsync -a "data/fixtures/" "$STAGING/data/fixtures/" 2>/dev/null || cp -R "data/fixtures/." "$STAGING/data/fixtures/"
  ok "copy: data/fixtures/"
fi

if [[ "$INCLUDE_SESSIONS" -eq 1 && -d "data/sessions" ]]; then
  mkdir -p "$STAGING/data/sessions"
  rsync -a "data/sessions/" "$STAGING/data/sessions/" 2>/dev/null || cp -R "data/sessions/." "$STAGING/data/sessions/"
  warn "copy: data/sessions/（已包含登录态 cookie，注意分发安全）"
else
  warn "skip: data/sessions（默认排除；如需请加 --include-sessions）"
fi

# ---------------------------- 4. MediaCrawler jsonl --------------------------
if [[ "$INCLUDE_MEDIACRAWLER" -eq 1 ]]; then
  for plat in xhs douyin; do
    src="third_party/MediaCrawler/data/${plat}/jsonl"
    if [[ -d "$src" ]]; then
      mkdir -p "$STAGING/$src"
      rsync -a "$src/" "$STAGING/$src/" 2>/dev/null || cp -R "$src/." "$STAGING/$src/"
      ok "copy: $src/"
    fi
  done
fi

# ---------------------------- 5. manifest.json -------------------------------
log "生成 manifest.json"
GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "")"
GIT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
HOSTNAME_VAL="$(hostname 2>/dev/null || echo "")"
EXPORTER="${USER:-unknown}"
TOTAL_SIZE_KB="$(du -sk "$STAGING" 2>/dev/null | awk '{print $1}')"

# 抓 sqlite 行数（关键表）
get_count() {
  local db="$1" tbl="$2"
  [[ -f "$db" ]] || { echo 0; return; }
  [[ -n "$SQLITE_BIN" ]] || { echo "?"; return; }
  "$SQLITE_BIN" "$db" "SELECT COUNT(*) FROM ${tbl};" 2>/dev/null || echo 0
}

ROWS_INTEL=$(get_count "$STAGING/data/intel_hub.sqlite" opportunity_cards)
ROWS_XHS=$(get_count "$STAGING/data/xhs_review.sqlite" xhs_opportunity_cards)
ROWS_PLAN=$(get_count "$STAGING/data/content_plan.sqlite" planning_sessions)
ROWS_GROWTH=$(get_count "$STAGING/data/growth_lab.sqlite" workspace_plans)
ROWS_VS_PACK=$(get_count "$STAGING/data/growth_lab.sqlite" visual_strategy_packs)
ROWS_NOTE_PACK=$(get_count "$STAGING/data/growth_lab.sqlite" note_packs)
ROWS_RULE=$(get_count "$STAGING/data/content_plan.sqlite" rule_specs)
ROWS_BRIEF=$(get_count "$STAGING/data/growth_lab.sqlite" creative_briefs)
ROWS_CAND=$(get_count "$STAGING/data/growth_lab.sqlite" strategy_candidates)
ROWS_FEEDBACK=$(get_count "$STAGING/data/growth_lab.sqlite" visual_feedback_records)

# JSON 大小
size_of() { [[ -f "$1" ]] && stat -f "%z" "$1" 2>/dev/null || stat -c "%s" "$1" 2>/dev/null || echo 0; }
SIZE_OPC="$(size_of "$STAGING/data/output/xhs_opportunities/opportunity_cards.json")"
SIZE_PDJ="$(size_of "$STAGING/data/output/xhs_opportunities/pipeline_details.json")"

# MediaCrawler 文件计数
MC_XHS_JSONL_COUNT=0
MC_DY_JSONL_COUNT=0
[[ -d "$STAGING/third_party/MediaCrawler/data/xhs/jsonl" ]] && MC_XHS_JSONL_COUNT="$(ls -1 "$STAGING/third_party/MediaCrawler/data/xhs/jsonl" 2>/dev/null | wc -l | tr -d ' ')"
[[ -d "$STAGING/third_party/MediaCrawler/data/douyin/jsonl" ]] && MC_DY_JSONL_COUNT="$(ls -1 "$STAGING/third_party/MediaCrawler/data/douyin/jsonl" 2>/dev/null | wc -l | tr -d ' ')"

cat > "$STAGING/manifest.json" <<EOF
{
  "schema_version": 1,
  "exported_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "exporter": "${EXPORTER}",
  "host": "${HOSTNAME_VAL}",
  "git_commit": "${GIT_COMMIT}",
  "git_branch": "${GIT_BRANCH}",
  "profile": "$( [[ $LITE -eq 1 ]] && echo lite || echo full )",
  "include_sessions": $INCLUDE_SESSIONS,
  "include_mediacrawler": $INCLUDE_MEDIACRAWLER,
  "include_raw": $INCLUDE_RAW,
  "include_fixtures": $INCLUDE_FIXTURES,
  "total_size_kb": ${TOTAL_SIZE_KB},
  "sqlite_rows": {
    "data/intel_hub.sqlite::opportunity_cards": ${ROWS_INTEL},
    "data/xhs_review.sqlite::xhs_opportunity_cards": ${ROWS_XHS},
    "data/content_plan.sqlite::planning_sessions": ${ROWS_PLAN},
    "data/content_plan.sqlite::rule_specs": ${ROWS_RULE},
    "data/growth_lab.sqlite::workspace_plans": ${ROWS_GROWTH},
    "data/growth_lab.sqlite::visual_strategy_packs": ${ROWS_VS_PACK},
    "data/growth_lab.sqlite::strategy_candidates": ${ROWS_CAND},
    "data/growth_lab.sqlite::creative_briefs": ${ROWS_BRIEF},
    "data/growth_lab.sqlite::note_packs": ${ROWS_NOTE_PACK},
    "data/growth_lab.sqlite::visual_feedback_records": ${ROWS_FEEDBACK}
  },
  "json_sizes": {
    "data/output/xhs_opportunities/opportunity_cards.json": ${SIZE_OPC},
    "data/output/xhs_opportunities/pipeline_details.json": ${SIZE_PDJ}
  },
  "mediacrawler_files": {
    "xhs_jsonl_count": ${MC_XHS_JSONL_COUNT},
    "douyin_jsonl_count": ${MC_DY_JSONL_COUNT}
  }
}
EOF
rm -f "$DB_ROWS_JSON"
ok "manifest 写入完成"

# ---------------------------- 6. 打包 ----------------------------------------
log "tar.gz 打包中..."
( cd "$STAGING" && tar -czf "$OUT_PATH" \
    --exclude='*.log' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='browser_data' \
    . )

OUT_SIZE_H="$(du -h "$OUT_PATH" 2>/dev/null | awk '{print $1}')"
ok "已生成: $OUT_PATH (${OUT_SIZE_H})"

# ---------------------------- 7. 总结 ----------------------------------------
cat <<EOF

${C_GREEN}===== 导出完成 =====${C_RESET}
  bundle      : ${OUT_PATH}
  size        : ${OUT_SIZE_H}
  git_commit  : ${GIT_COMMIT:-<none>}
  XHS 机会卡  : ${ROWS_XHS} 张（xhs_review.sqlite）
  规划会话    : ${ROWS_PLAN} 条（content_plan.sqlite）
  视觉策略包  : ${ROWS_VS_PACK} 个（growth_lab.sqlite）
  候选/Brief : ${ROWS_CAND}/${ROWS_BRIEF}
  NotePack    : ${ROWS_NOTE_PACK}
  规则        : ${ROWS_RULE} 条
  反馈        : ${ROWS_FEEDBACK} 条
  MediaCrawler XHS jsonl: ${MC_XHS_JSONL_COUNT} 个

下一步（在客户侧服务器）：
  scp "${OUT_PATH}" user@server:/tmp/
  ssh user@server "bash /opt/ontology-os/scripts/bootstrap_data.sh \\
       --bundle /tmp/$(basename "$OUT_PATH") --mode safe --restart-service"

EOF
