"""ExpertAssetLoader — 从 assets/ 目录加载专家富模板资产。

支持 4 类解析器：
- YAML Schema v2：assets/主图&详情策划模板/主图策划/*.yaml
- 详情页 MD（表格）：assets/主图&详情策划模板/详情页策划/*.md
- 视频 MD（分镜 + 阶段文案）：assets/视频生成/*.md
- 买家秀 MD（场景 + 8 张）：assets/买家秀/*.md
- 竞品 MD（维度列表）：assets/竞品主图拆解/*.md

每个解析器独立判别是否能吃下某文件，能就返回 ScriptTemplate。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from apps.growth_lab.schemas.visual_workspace import ScriptTemplate, TemplateSlot

logger = logging.getLogger(__name__)

ASSETS_ROOT = Path(__file__).resolve().parents[3] / "assets"


# ── 工具 ──────────────────────────────────────────────

def _slugify(text: str, fallback: str = "") -> str:
    s = re.sub(r"[^\w\u4e00-\u9fa5]+", "_", text.strip()).strip("_")
    return s or fallback


def _read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flatten(parts: list[str]) -> str:
    return "；".join(p.strip() for p in parts if p and p.strip())


def _normalize_aspect(value: Any) -> str:
    """兼容 YAML 1.1 把 `1:1` 解析为 sexagesimal（61）的情况。

    常见宽高比 1:1 / 3:4 / 4:3 / 16:9 / 9:16 对应的 60 进制整数：
      61, 184, 243, 969, 554 — 我们通过 size hint 反推。
    保守做法：只还原最常见的几种，否则原样 str(value)。
    """
    if isinstance(value, str):
        return value
    mapping = {61: "1:1", 184: "3:4", 243: "4:3", 969: "16:9", 554: "9:16"}
    if isinstance(value, int) and value in mapping:
        return mapping[value]
    if isinstance(value, float):
        # 形如 1.1 这种罕见
        return str(value)
    return str(value) if value is not None else "1:1"


# ── 解析器基类 ──────────────────────────────────────────


class AssetParser:
    source_kind: str = "base"

    def can_parse(self, path: Path) -> bool:  # pragma: no cover
        return False

    def parse(self, path: Path) -> ScriptTemplate | None:  # pragma: no cover
        return None


# ── YAML Schema v2（主图脚本资产统一 Schema v2） ──────────────


class MainImageV2YamlParser(AssetParser):
    """主图脚本资产统一 Schema v2 解析器。"""

    source_kind = "yaml_v2"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yaml", ".yml"}:
            return False
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
        except Exception:
            return False
        return (
            raw.get("schema_version") == "main_image_script_v2"
            or raw.get("asset_type") == "main_image_script_bundle"
        )

    def parse(self, path: Path) -> ScriptTemplate | None:
        with path.open("r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}

        cards = raw.get("cards") or []
        slots: list[TemplateSlot] = []
        for c in cards:
            vs = c.get("visual_spec") or {}
            cs = c.get("copy_spec") or {}
            cp = c.get("compile_spec") or {}

            visual_text_parts: list[str] = []
            if vs.get("scene"):
                visual_text_parts.append(str(vs["scene"]))
            for sub in vs.get("subjects") or []:
                if sub.get("description"):
                    visual_text_parts.append(f"{sub.get('role','')}：{sub['description']}")
            if vs.get("labels"):
                visual_text_parts.append("标签：" + "、".join(vs["labels"]))
            visual_text = _flatten(visual_text_parts)

            copy_parts: list[str] = []
            if cs.get("headline"):
                copy_parts.append(f"主标题：{cs['headline']}")
            if cs.get("subheadline"):
                copy_parts.append(f"副标题：{cs['subheadline']}")
            if cs.get("selling_points"):
                copy_parts.append("卖点：" + "、".join(cs["selling_points"]))
            copy_text = _flatten(copy_parts)

            slot = TemplateSlot(
                index=int(c.get("order", 0) or 0),
                role=c.get("title") or c.get("card_type") or "",
                visual_spec=visual_text,
                copy_spec=copy_text,
                aspect_ratio=_normalize_aspect(
                    (cp.get("render_hints") or {}).get("aspect_ratio", "1:1")
                ),
                positive_prompt_blocks=list(cp.get("positive_prompt_blocks") or []),
                negative_prompt_blocks=list(cp.get("negative_prompt_blocks") or []),
                headline=cs.get("headline") or "",
                subheadline=cs.get("subheadline") or "",
                selling_points=list(cs.get("selling_points") or []),
                labels=list(vs.get("labels") or []),
                evaluation_criteria=list(
                    ((raw.get("script_asset") or {}).get("evaluation_policy") or {}).get(
                        "required_dimensions", []
                    )
                ),
                extra={
                    "card_id": c.get("card_id", ""),
                    "card_type": c.get("card_type", ""),
                    "objective": c.get("objective", ""),
                    "message_role": c.get("message_role", ""),
                    "composition": vs.get("composition") or {},
                    "background": vs.get("background") or {},
                    "lighting": vs.get("lighting") or {},
                    "tags": c.get("tags") or {},
                    "prompt_intent": cp.get("prompt_intent") or "",
                },
            )
            slots.append(slot)

        # 品牌规则：从 global_style.avoid_keywords + strategy_pack 抽取
        brand_rules: list[str] = []
        gs = raw.get("global_style") or {}
        if gs.get("color_system"):
            cs_dict = gs["color_system"]
            brand_rules.append(
                f"主色：{cs_dict.get('primary','')}；辅色：{cs_dict.get('secondary','')}"
            )
        if gs.get("tone"):
            brand_rules.append(f"整体基调：{gs['tone']}")
        if gs.get("avoid_keywords"):
            brand_rules.append("避免：" + "、".join(gs["avoid_keywords"]))

        template_id = raw.get("asset_id") or path.stem
        return ScriptTemplate(
            template_id=template_id,
            category="main_image",
            name=raw.get("title") or path.stem,
            description=(raw.get("description") or "").strip(),
            slots=sorted(slots, key=lambda s: s.index),
            default_brand_rules=brand_rules,
            yaml_source_path=str(path),
            version=str(raw.get("version", "v2")),
            business_context=raw.get("business_context") or {},
            strategy_pack=raw.get("strategy_pack") or {},
            global_style=gs,
            script_asset=raw.get("script_asset") or {},
            prompt_compile_spec=raw.get("prompt_compile_spec") or {},
            review_spec=raw.get("review_spec") or {},
            lineage=raw.get("lineage") or {},
            source_kind=self.source_kind,
        )


# ── 详情页 MD（模块脚本表格） ─────────────────────────────


class DetailModuleMdParser(AssetParser):
    source_kind = "md_table"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".md":
            return False
        if "详情页" not in str(path):
            return False
        text = _read_md(path)
        return "## 模块脚本" in text and "| 序号 " in text

    def parse(self, path: Path) -> ScriptTemplate | None:
        text = _read_md(path)
        rows = _extract_md_table(text, section_title="模块脚本")
        if not rows:
            return None

        slots: list[TemplateSlot] = []
        for r in rows:
            idx_raw = (r.get("序号") or "").strip()
            try:
                idx = int(idx_raw)
            except ValueError:
                continue
            name = r.get("模块名称", "").strip()
            title = r.get("主标题", "").strip()
            subtitle = r.get("副标题", "").strip()
            visual = r.get("视觉重点描述", "").strip()
            sp = r.get("对应卖点", "").strip()

            slots.append(
                TemplateSlot(
                    index=idx,
                    role=name,
                    visual_spec=visual,
                    copy_spec=_flatten(
                        [
                            f"主标题：{title}" if title else "",
                            f"副标题：{subtitle}" if subtitle else "",
                            f"卖点：{sp}" if sp else "",
                        ]
                    ),
                    aspect_ratio="3:4",
                    headline=title,
                    subheadline=subtitle,
                    selling_points=[s.strip() for s in sp.split("、") if s.strip()],
                    positive_prompt_blocks=[p for p in [visual, title] if p],
                    negative_prompt_blocks=["信息过载", "版式混乱", "低质感"],
                    extra={"module_name": name},
                )
            )

        meta = _extract_bullets(text, "## 基本信息")
        description = _extract_first_blockquote(text)

        return ScriptTemplate(
            template_id=f"detail_report_{_slugify(path.stem, 'md')}"[:64],
            category="brand_detail_report",
            name=_first_heading(text) or path.stem,
            description=description,
            slots=sorted(slots, key=lambda s: s.index),
            default_brand_rules=["主图信息密度均衡", "一屏一卖点", "品牌符号稳定出现"],
            yaml_source_path=str(path),
            version="v1",
            extra={"meta_bullets": meta},
            source_kind=self.source_kind,
        )


# ── 视频 MD（分镜表 + 阶段文案） ─────────────────────────────


class VideoShotMdParser(AssetParser):
    source_kind = "md_table"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".md":
            return False
        if "视频" not in str(path):
            return False
        return "脚本分镜" in _read_md(path)

    def parse(self, path: Path) -> ScriptTemplate | None:
        text = _read_md(path)
        rows = _extract_md_table(text, section_title="脚本分镜")
        if not rows:
            return None

        # 阶段文案
        stage_copy = _extract_stage_copy(text)

        slots: list[TemplateSlot] = []
        for r in rows:
            idx_raw = (r.get("序号") or "").strip()
            try:
                idx = int(idx_raw)
            except ValueError:
                continue
            stage = r.get("分镜阶段", "").strip()
            scene = r.get("场景", "").strip()
            shot = r.get("景别", "").strip()
            product_on = r.get("出镜产品", "").strip()
            people_on = r.get("出镜人物", "").strip()

            copy_lines = stage_copy.get(stage, [])
            slots.append(
                TemplateSlot(
                    index=idx,
                    role=f"镜头{idx} · {stage}",
                    visual_spec=_flatten([scene, shot, product_on, people_on]),
                    copy_spec=_flatten(copy_lines),
                    aspect_ratio="9:16",
                    positive_prompt_blocks=[scene, stage, shot],
                    negative_prompt_blocks=["镜头抖动感", "光线脏乱"],
                    extra={
                        "stage": stage,
                        "shot_type": shot,
                        "product_presence": product_on,
                        "character_presence": people_on,
                    },
                )
            )

        return ScriptTemplate(
            template_id=f"video_{_slugify(path.stem,'md')}"[:64],
            category="video_shot_list",
            name=_first_heading(text) or path.stem,
            description=_extract_first_blockquote(text),
            slots=sorted(slots, key=lambda s: s.index),
            default_brand_rules=["单镜头 2-4s", "场景连贯", "口播贴合画面"],
            yaml_source_path=str(path),
            version="v1",
            extra={"stage_copy": stage_copy},
            source_kind=self.source_kind,
        )


# ── 买家秀 MD（场景 + 8 张分镜） ────────────────────────────


class BuyerShowMdParser(AssetParser):
    source_kind = "md_sections"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".md":
            return False
        text = _read_md(path)
        return "买家秀" in text and "张图片" in text

    def parse(self, path: Path) -> ScriptTemplate | None:
        text = _read_md(path)

        # 场景全景描述（第一节）
        scene_block = _extract_section(text, r"## 场景 1[：:]")
        scene_info = _flatten(
            [line.lstrip("- ").strip() for line in scene_block.splitlines()
             if line.strip().startswith("-")]
        )

        slots: list[TemplateSlot] = []
        pattern = re.compile(r"### (\d+)\.\s*([^\n]+)\n+((?:- [^\n]+\n?)+)", re.MULTILINE)
        for m in pattern.finditer(text):
            idx = int(m.group(1))
            role = m.group(2).strip()
            bullets_raw = m.group(3).strip()
            bullets = [
                re.sub(r"^\s*-\s*\*\*[^*]+\*\*[：:]?", "", ln).strip()
                for ln in bullets_raw.splitlines() if ln.strip()
            ]
            goal = _flatten(bullets)
            visual = _flatten([scene_info, goal])
            slots.append(
                TemplateSlot(
                    index=idx,
                    role=role,
                    visual_spec=visual,
                    copy_spec="",  # 买家秀以画面为主，无固定文案
                    aspect_ratio="3:4",
                    positive_prompt_blocks=[role, goal, scene_info],
                    negative_prompt_blocks=["广告感", "过度摆拍", "不自然"],
                    extra={"goal": goal},
                )
            )

        return ScriptTemplate(
            template_id=f"buyer_show_{_slugify(path.stem,'md')}"[:64],
            category="buyer_show",
            name=_first_heading(text) or path.stem,
            description=_extract_first_blockquote(text),
            slots=sorted(slots, key=lambda s: s.index),
            default_brand_rules=["真实生活感", "人物姿态自然", "场景一致"],
            yaml_source_path=str(path),
            version="v1",
            extra={"scene_profile": scene_info},
            source_kind=self.source_kind,
        )


# ── 竞品 MD（32 维度框架） ────────────────────────────────


class CompetitorMdParser(AssetParser):
    source_kind = "md_sections"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() != ".md":
            return False
        text = _read_md(path)
        return "竞品" in text and "主体与构图" in text

    def parse(self, path: Path) -> ScriptTemplate | None:
        text = _read_md(path)
        sections = re.findall(
            r"##\s+[一二三四五六七八]+、([^\n]+)\n+((?:-\s+[^\n]+\n?)+)",
            text,
        )
        slots: list[TemplateSlot] = []
        idx = 1
        for group_name, bullet_block in sections:
            dims = [
                ln.lstrip("- ").strip()
                for ln in bullet_block.splitlines() if ln.strip().startswith("-")
            ]
            slots.append(
                TemplateSlot(
                    index=idx,
                    role=group_name.strip(),
                    visual_spec=_flatten(dims),
                    copy_spec="",
                    aspect_ratio="1:1",
                    extra={"dimension_group": group_name.strip(), "dimensions": dims},
                )
            )
            idx += 1

        return ScriptTemplate(
            template_id=f"competitor_{_slugify(path.stem,'md')}"[:64],
            category="competitor_deconstruct",
            name=_first_heading(text) or path.stem,
            description=_extract_first_blockquote(text),
            slots=slots,
            default_brand_rules=["覆盖 4 组 32 维度"],
            yaml_source_path=str(path),
            version="v1",
            source_kind=self.source_kind,
        )


# ── 通用工具：MD 表格 / 段落抽取 ─────────────────────────────


def _first_heading(text: str) -> str:
    m = re.search(r"^#\s+([^\n]+)", text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_first_blockquote(text: str) -> str:
    m = re.search(r"^>\s*([^\n]+)", text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_bullets(text: str, heading: str) -> list[str]:
    # 抓取 heading 之后、下一个 ## 之前的 `-` 列表项
    block = _extract_section(text, re.escape(heading))
    return [ln.lstrip("- ").strip() for ln in block.splitlines() if ln.strip().startswith("-")]


def _extract_section(text: str, heading_pattern: str) -> str:
    m = re.search(rf"{heading_pattern}[^\n]*\n(.*?)(?=\n## |\Z)", text, flags=re.DOTALL)
    return m.group(1) if m else ""


def _extract_md_table(text: str, *, section_title: str) -> list[dict[str, str]]:
    block = _extract_section(text, re.escape(section_title))
    if not block:
        return []
    lines = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = [h.strip() for h in lines[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for ln in lines[2:]:  # 跳过分隔行
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells, strict=False)))
    return rows


def _extract_stage_copy(text: str) -> dict[str, list[str]]:
    """从 '阶段文案拆解' 章节读取各阶段对应 copy。"""
    stage_map: dict[str, list[str]] = {}
    block = _extract_section(text, "阶段文案拆解")
    if not block:
        return stage_map
    # ### N. 阶段名 \n - xxx\n - yyy
    for m in re.finditer(
        r"###\s+\d+\.\s*([^\n]+)\n+((?:-\s+[^\n]+\n?)+)",
        block,
    ):
        stage_name = m.group(1).strip()
        bullets = [
            ln.lstrip("- ").strip()
            for ln in m.group(2).splitlines() if ln.strip().startswith("-")
        ]
        stage_map[stage_name] = bullets
    return stage_map


# ── 加载器入口 ────────────────────────────────────────────


PARSERS: list[AssetParser] = [
    MainImageV2YamlParser(),
    DetailModuleMdParser(),
    VideoShotMdParser(),
    BuyerShowMdParser(),
    CompetitorMdParser(),
]


def load_expert_assets(root: Path | None = None) -> list[ScriptTemplate]:
    """递归扫描 assets/，返回所有成功解析的 ScriptTemplate。"""
    root = root or ASSETS_ROOT
    results: list[ScriptTemplate] = []
    if not root.exists():
        logger.warning("资产目录不存在: %s", root)
        return results

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".yaml", ".yml"}:
            continue
        for parser in PARSERS:
            try:
                if not parser.can_parse(path):
                    continue
                tpl = parser.parse(path)
                if tpl is None:
                    continue
                results.append(tpl)
                logger.info(
                    "[expert_asset] 已加载: %s ← %s (%d slots, kind=%s)",
                    tpl.template_id, path.name, len(tpl.slots), tpl.source_kind,
                )
                break
            except Exception as exc:
                logger.exception("[expert_asset] 解析失败: %s ← %s", path, exc)
    return results
