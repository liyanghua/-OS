"""LLM-driven CategoryLens YAML draft generator.

Workflow:
    user CLI -> generate_lens(category, ...)
            -> render prompt (system + user)
            -> llm_router.chat (default provider: deepseek)
            -> lenient JSON parse
            -> CategoryLens.model_validate (Pydantic)
            -> on ValidationError, feed error back into next attempt
            -> on success, dump YAML to build/lens_drafts/<lens_id>.yaml
            -> emit <lens_id>.review.md with manual checklist

The draft directory is intentionally NOT under config/category_lenses/
so that LLM-fabricated content cannot contaminate production routing
until a human moves the file over.

CLI::

    DEEPSEEK_API_KEY=... python -m apps.intel_hub.services.lens_generator \\
        --category "儿童桌垫" \\
        --lens-id children_desk_mat \\
        --reference tablecloth \\
        --provider deepseek
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from apps.content_planning.adapters.llm_router import (
    LLMMessage,
    LLMResponse,
    LLMRouter,
    llm_router as _default_router,
)
from apps.intel_hub.config_loader import REPO_ROOT
from apps.intel_hub.domain.category_lens import CategoryLens

logger = logging.getLogger(__name__)


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "generate_category_lens.md"
DEFAULT_DRAFTS_DIR = REPO_ROOT / "build" / "lens_drafts"
DEFAULT_REFERENCE_LENS = "tablecloth"


class LensGenerationError(RuntimeError):
    """LLM 调用 / Pydantic 校验持续失败时抛出。"""


# ── Helpers ────────────────────────────────────────────────────────


def _load_dotenv_if_present() -> None:
    """Best-effort .env loader so ``DEEPSEEK_API_KEY`` etc. are visible without
    asking the user to ``source`` anything before running the CLI.

    Only sets vars that are not already in ``os.environ``.
    """
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as exc:
        logger.warning("[lens_generator] .env load skipped: %s", exc)


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
    return cleaned.strip("_").lower() or "category"


def _load_prompt_sections(prompt_path: Path = PROMPT_PATH) -> tuple[str, str]:
    raw = prompt_path.read_text(encoding="utf-8")
    sys_match = re.search(
        r"##\s*SYSTEM\s*\n(.*?)(?=\n##\s|\Z)",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    user_match = re.search(
        r"##\s*USER\s*\n(.*?)(?=\n##\s|\Z)",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not sys_match or not user_match:
        raise LensGenerationError(f"Prompt 文件 {prompt_path} 缺少 SYSTEM/USER 段")
    return sys_match.group(1).strip(), user_match.group(1).strip()


def _load_reference_lens_yaml(reference_lens_id: str) -> str:
    candidate = REPO_ROOT / "config" / "category_lenses" / f"{reference_lens_id}.yaml"
    if not candidate.exists():
        raise LensGenerationError(f"参考 lens 不存在：{candidate}")
    return candidate.read_text(encoding="utf-8")


def _describe_schema_fields() -> str:
    schema = CategoryLens.model_json_schema()
    properties: dict[str, Any] = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    lines: list[str] = []
    for name, prop in properties.items():
        if "type" in prop:
            kind = prop["type"]
        elif "$ref" in prop:
            kind = prop["$ref"].split("/")[-1]
        elif "anyOf" in prop:
            kind = " | ".join(
                str(x.get("type") or x.get("$ref", "any")).split("/")[-1]
                for x in prop["anyOf"]
            )
        else:
            kind = "any"
        flag = "[required]" if name in required else "[optional]"
        lines.append(f"- {name} {flag}: {kind}")
    return "\n".join(lines)


def _lenient_parse(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("\n")
        end_idx = len(parts) - 1 if parts[-1].strip().startswith("```") else len(parts)
        cleaned = "\n".join(parts[1:end_idx]).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{", cleaned)
    if not match:
        return {}
    candidate = cleaned[match.start():]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        depth_brace = candidate.count("{") - candidate.count("}")
        depth_bracket = candidate.count("[") - candidate.count("]")
        patched = candidate.rstrip().rstrip(",")
        patched += "]" * max(depth_bracket, 0)
        patched += "}" * max(depth_brace, 0)
        try:
            return json.loads(patched)
        except json.JSONDecodeError:
            return {}


def _render_user_prompt(
    *,
    user_template: str,
    category_cn: str,
    lens_id: str,
    core_logic_hint: str,
    reference_lens_id: str,
    reference_lens_yaml: str,
    schema_field_list: str,
    prior_error_hint: str,
) -> str:
    return user_template.format(
        category_cn=category_cn,
        lens_id=lens_id,
        core_logic_hint=core_logic_hint or "（未提供，自行根据品类常识填写）",
        reference_lens_id=reference_lens_id,
        reference_lens_yaml=reference_lens_yaml,
        schema_field_list=schema_field_list,
        prior_error_hint=prior_error_hint,
    )


def _post_normalize(
    data: dict[str, Any],
    *,
    lens_id: str,
    category_cn: str,
) -> dict[str, Any]:
    """避免 LLM 改 lens_id / category_cn，导致下游 routing 错位。"""
    out = dict(data)
    out["lens_id"] = lens_id
    out["category_cn"] = category_cn
    return out


# ── Core API ──────────────────────────────────────────────────────


def generate_lens(
    *,
    category_cn: str,
    lens_id: str | None = None,
    core_logic_hint: str = "",
    reference_lens: str = DEFAULT_REFERENCE_LENS,
    provider: str = "deepseek",
    model: str | None = None,
    max_retries: int = 2,
    output_dir: Path | str | None = None,
    router: LLMRouter | None = None,
) -> Path:
    """生成 CategoryLens YAML 草稿，落到 ``build/lens_drafts/``。

    Returns:
        草稿 yaml 文件的绝对路径；同目录下还有 ``<lens_id>.review.md``。

    Raises:
        LensGenerationError: 连续 ``max_retries + 1`` 次仍未通过 Pydantic 校验。
    """
    _load_dotenv_if_present()
    lens_id_val = lens_id or _slugify(category_cn)
    drafts_dir = Path(output_dir) if output_dir else DEFAULT_DRAFTS_DIR
    if not drafts_dir.is_absolute():
        drafts_dir = REPO_ROOT / drafts_dir
    drafts_dir.mkdir(parents=True, exist_ok=True)

    system_prompt, user_template = _load_prompt_sections()
    reference_yaml = _load_reference_lens_yaml(reference_lens)
    schema_fields = _describe_schema_fields()
    used_router = router or _default_router

    prior_error_hint = ""
    last_response: LLMResponse | None = None
    last_error: str = ""

    for attempt in range(max_retries + 1):
        user_prompt = _render_user_prompt(
            user_template=user_template,
            category_cn=category_cn,
            lens_id=lens_id_val,
            core_logic_hint=core_logic_hint,
            reference_lens_id=reference_lens,
            reference_lens_yaml=reference_yaml,
            schema_field_list=schema_fields,
            prior_error_hint=prior_error_hint,
        )
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        logger.info(
            "[lens_generator] attempt=%d provider=%s lens_id=%s",
            attempt + 1, provider, lens_id_val,
        )
        response = used_router.chat(
            messages,
            provider=provider,
            model=model,
            temperature=0.2,
            max_tokens=4000,
        )
        last_response = response
        if response.degraded or not response.content.strip():
            last_error = response.degraded_reason or "empty_response"
            prior_error_hint = (
                f"上一轮 LLM 调用失败：{last_error}，请重新输出符合 schema 的完整 JSON。"
            )
            continue

        parsed = _lenient_parse(response.content)
        if not parsed:
            last_error = "lenient_json_parse_returned_empty"
            prior_error_hint = (
                "上一轮输出无法解析为 JSON，请只输出一个 JSON 对象，不要 Markdown 围栏，不要解释。"
            )
            continue

        normalized = _post_normalize(parsed, lens_id=lens_id_val, category_cn=category_cn)
        try:
            lens = CategoryLens.model_validate(normalized)
        except ValidationError as exc:
            last_error = str(exc)
            prior_error_hint = (
                "上一轮 JSON 未通过 CategoryLens schema 校验，错误如下，请修正并重新输出完整 JSON：\n"
                f"{textwrap.shorten(str(exc), width=1500, placeholder=' ...')}"
            )
            continue

        return _write_outputs(
            lens=lens,
            response=response,
            provider=provider,
            drafts_dir=drafts_dir,
        )

    snippet = (last_response.content if last_response else "")[:300]
    raise LensGenerationError(
        f"LLM 生成 lens 连续 {max_retries + 1} 次失败：{last_error}\n"
        f"最后一次响应 (model={getattr(last_response, 'model', '-')}, "
        f"provider={getattr(last_response, 'provider', '-')}): {snippet}"
    )


def _write_outputs(
    *,
    lens: CategoryLens,
    response: LLMResponse,
    provider: str,
    drafts_dir: Path,
) -> Path:
    yaml_path = drafts_dir / f"{lens.lens_id}.yaml"
    review_path = drafts_dir / f"{lens.lens_id}.review.md"
    payload = lens.model_dump(mode="python")
    yaml_text = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")
    review_path.write_text(
        _render_review_report(lens, response, provider),
        encoding="utf-8",
    )
    logger.info("[lens_generator] wrote draft=%s review=%s", yaml_path, review_path)
    return yaml_path


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _empty_top_level_fields(lens: CategoryLens) -> list[str]:
    payload = lens.model_dump(mode="python")
    return [name for name, value in payload.items() if _is_empty(value)]


def _render_review_report(
    lens: CategoryLens,
    response: LLMResponse,
    provider: str,
) -> str:
    payload = lens.model_dump(mode="python")
    empty_fields = _empty_top_level_fields(lens)
    fill_rate = 1.0 - (len(empty_fields) / max(len(payload), 1))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# Lens 草稿 review — `{lens.lens_id}`",
        "",
        f"- 生成时间：{timestamp}",
        f"- 类目中文名：{lens.category_cn}",
        f"- LLM provider：{provider}",
        f"- LLM model：{response.model or '-'}",
        f"- 实际 elapsed：{response.elapsed_ms} ms",
        f"- 字段填充率：{fill_rate:.0%}（{len(payload) - len(empty_fields)}/{len(payload)} 顶层字段非空）",
        "",
        "## 必检 checklist",
        "- [ ] price_bands 是否合理？LLM 易瞎编价格，不确定就清空 `range_cny`",
        "- [ ] keyword_aliases 是否覆盖站内常见搜索词、是否有竞品干扰词混入",
        "- [ ] **keyword_aliases 不要含上位品类词**（例如儿童桌垫不要含「桌垫」「桌布」，否则会被路由到错误品类）",
        "- [ ] visual_prompt_hints / text_lexicons 是否符合行业常识",
        "- [ ] user_expression_map 是否含真实买家原话风格",
        "- [ ] 没有「占位符 / TODO / xxx / 示例」残留",
        "- [ ] scoring_weights 八项总和接近 1.0、按品类特性偏重",
        "",
        "## 自动检测",
    ]
    if empty_fields:
        lines.append(f"- ⚠️ 顶层空字段：{', '.join(empty_fields)}（建议补齐或确认确实不需要）")
    else:
        lines.append("- ✅ 顶层字段均已填充")

    if any(not pb.range_cny for pb in lens.price_bands):
        lines.append(
            "- ⚠️ 部分 price_band 的 range_cny 为空（LLM 不确定价格时的合理表现，review 时可补真实价格带）"
        )

    if not lens.user_expression_map:
        lines.append(
            "- ⚠️ user_expression_map 为空 → 下游 prompt 难以注入真实买家口吻"
        )

    if not lens.text_lexicons.scene_words:
        lines.append(
            "- ⚠️ text_lexicons.scene_words 为空 → signal_extractor 会回退到桌布默认词库"
        )

    lines.extend([
        "",
        "## review 通过后",
        "",
        "```bash",
        f"mv build/lens_drafts/{lens.lens_id}.yaml config/category_lenses/",
        "```",
        "",
        "然后到 `config/category_lenses/_keyword_routing.yaml` / "
        "`config/ontology_mapping.yaml` / `config/watchlists.yaml` 同步加路由 / 实体 / watchlist。",
    ])
    return "\n".join(lines) + "\n"


# ── CLI ────────────────────────────────────────────────────────────


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LLM-driven CategoryLens YAML draft generator",
    )
    parser.add_argument("--category", required=True, help="品类中文名，如「儿童桌垫」")
    parser.add_argument(
        "--lens-id", default=None,
        help="英文 lens_id（默认从 category 派生）",
    )
    parser.add_argument(
        "--core-logic", default="",
        help="品类核心消费逻辑提示（可空），传给 LLM 的 hint",
    )
    parser.add_argument(
        "--reference", default=DEFAULT_REFERENCE_LENS,
        help=f"作为 schema 参考的现有 lens_id（默认 {DEFAULT_REFERENCE_LENS}）",
    )
    parser.add_argument(
        "--provider", default="deepseek",
        choices=["deepseek", "openai", "anthropic", "dashscope"],
        help="LLM provider（默认 deepseek）",
    )
    parser.add_argument(
        "--model", default=None,
        help="模型 id（默认按 provider 的环境变量决定）",
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="LLM/校验失败重试轮数（默认 2）",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="草稿目录（默认 build/lens_drafts/）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s | %(message)s")
    args = _build_arg_parser().parse_args(argv)
    try:
        path = generate_lens(
            category_cn=args.category,
            lens_id=args.lens_id,
            core_logic_hint=args.core_logic,
            reference_lens=args.reference,
            provider=args.provider,
            model=args.model,
            max_retries=args.max_retries,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    except LensGenerationError as exc:
        logger.error("生成失败：%s", exc)
        return 1
    review = path.with_name(path.stem + ".review.md")
    print(f"草稿生成成功：{path}")
    print(f"review 报告：{review}")
    print("人工 review 后用：")
    print(f"  mv {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}"
          f" config/category_lenses/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
