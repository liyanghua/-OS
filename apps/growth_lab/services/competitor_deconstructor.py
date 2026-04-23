"""CompetitorDeconstructor — 竞品主图 32 维度 VLM 拆解器。

输入：竞品图片 URL（公网 http(s) 或本地 /source-images/、/generated-images/ 路径）
输出：按 competitor_deconstruct_32d 模板 4 组共 32 维度的结构化分析 + 对标本品的差异点。

调用真实多模态 VLM（OpenRouter 优先，`OPENAI_BASE_URL` 代理作回退），
把图片以 image_url 内容块传入，保证 VLM 真正“看见”图；
LLM 不可用 / 解析失败时返回规则降级（32 维空值骨架），让前端仍能渲染画布节点。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
你是一位资深电商视觉拆解专家，按 32 个维度分析竞品主图。
输入是一张竞品主图（通过 image_url 传入），请认真观察图片，从以下四组共 32 个维度输出结构化分析。
每个维度必须基于你对该图片的实际观察给出具体、简短的描述（≤20 字），不要留空、不要用“无/N/A”。

严格输出纯 JSON（不要 code fence、不要多余文字）：
{
  "composition_color": {
    "主体物位置": "...", "构图方式": "...", "层次关系": "...", "主色调": "...",
    "辅助色": "...", "色彩对比": "...", "色彩情绪": "...", "产品占比": "..."
  },
  "display_copy": {
    "展示角度": "...", "展示数量": "...", "细节呈现": "...", "标题文字": "...",
    "促销信息": "...", "卖点文案": "...", "文字位置": "...", "文字占比": "..."
  },
  "background_mood": {
    "背景类型": "...", "背景颜色": "...", "简洁程度": "...", "氛围营造": "...",
    "装饰元素": "...", "图标标识": "...", "边框修饰": "...", "特效处理": "..."
  },
  "scene_quality": {
    "使用场景": "...", "人物元素": "...", "生活化元素": "...", "场景道具": "...",
    "图片清晰度": "...", "光影处理": "...", "精致程度": "...", "专业度": "..."
  },
  "summary": "一句话总结竞品主图的差异化打法（≤40字）",
  "borrow_ideas": ["可借鉴点1", "可借鉴点2"],
  "avoid_ideas": ["应规避点1"]
}
"""

_USER_HINT = (
    "请仔细观察这张竞品主图，按系统提示给出的 JSON 结构填充 32 维分析，"
    "每个维度用你实际观察到的视觉特征来写具体描述，不要留空。"
)

_DEFAULT_VLM_MODEL = "google/gemini-2.5-flash"
_DEFAULT_QWEN_VL_MODEL = "qwen-vl-max-latest"


class CompetitorDeconstructor:
    """VLM 竞品拆解器。"""

    async def deconstruct(self, image_url: str) -> dict:
        """分析一张竞品图；VLM 不可用或解析失败时返回空骨架。"""
        if not image_url:
            return self._empty_skeleton(reason="empty_url")

        ref_url = self._resolve_ref_url(image_url)
        if not ref_url:
            return self._empty_skeleton(reason="local_image_not_found")

        providers = self._candidate_providers()
        if not providers:
            logger.warning(
                "[CompetitorDeconstructor] 未配置 VLM 提供方（OPENROUTER_API_KEY / OPENAI_BASE_URL 均缺失）"
            )
            return self._empty_skeleton(reason="no_vision_provider")

        last_reason = "vlm_error"
        for provider, model, api_key, base_url in providers:
            try:
                raw_content = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=provider, m=model, k=api_key, b=base_url: self._call_vlm_sync(
                        provider=p, model=m, api_key=k, base_url=b, ref_url=ref_url,
                    ),
                )
            except Exception as exc:
                last_reason = f"vlm_error:{exc}"
                logger.warning(
                    "[CompetitorDeconstructor] VLM 调用失败 provider=%s model=%s base=%s err=%s(%s); 尝试下一个",
                    provider, model, base_url, type(exc).__name__, exc,
                )
                continue

            parsed = self._safe_json(raw_content)
            if not parsed:
                last_reason = "json_parse_failed"
                logger.warning(
                    "[CompetitorDeconstructor] VLM 响应无法解析 JSON provider=%s model=%s preview=%s",
                    provider, model, (raw_content or "")[:200],
                )
                continue

            parsed["image_url"] = image_url
            parsed["provider"] = f"{provider}:{model}"
            return parsed

        return self._empty_skeleton(reason=last_reason)

    @staticmethod
    def _candidate_providers() -> list[tuple[str, str, str, str]]:
        """按优先级返回候选 VLM 提供方列表 [(provider, model, api_key, base_url), ...]。

        顺序：DashScope Qwen-VL（国内直连、稳定） → 用户自建 OPENAI_BASE_URL 代理 → OpenRouter。
        任一 provider 失败（异常 / 解析失败）会自动回退到下一个。
        """
        candidates: list[tuple[str, str, str, str]] = []
        default_vlm = os.environ.get("COMPETITOR_VLM_MODEL", "").strip() or _DEFAULT_VLM_MODEL

        dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
        if dashscope_key:
            qwen_model = (
                os.environ.get("COMPETITOR_VLM_MODEL_QWEN", "").strip()
                or _DEFAULT_QWEN_VL_MODEL
            )
            qwen_base = (
                os.environ.get("DASHSCOPE_BASE_URL", "").strip()
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            candidates.append(("dashscope_qwen_vl", qwen_model, dashscope_key, qwen_base))

        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        openai_base = os.environ.get("OPENAI_BASE_URL", "").strip()
        if openai_key and openai_base:
            openai_model = os.environ.get("OPENAI_MODEL", "").strip() or default_vlm
            candidates.append(("openai_proxy", openai_model, openai_key, openai_base))

        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if openrouter_key:
            candidates.append(("openrouter", default_vlm, openrouter_key, "https://openrouter.ai/api/v1"))

        return candidates

    @staticmethod
    def _resolve_ref_url(image_url: str) -> str:
        """本地服务路径（/source-images/, /generated-images/, 裸路径）转 data URI；http(s) 原样返回。"""
        if not image_url:
            return ""
        if image_url.startswith(("http://", "https://", "data:")):
            return image_url
        try:
            from apps.content_planning.services.image_generator import ImageGeneratorService
        except Exception as exc:  # pragma: no cover
            logger.warning("[CompetitorDeconstructor] 无法导入 ImageGeneratorService: %s", exc)
            return ""
        data_uri = ImageGeneratorService._local_path_to_data_uri(image_url)
        return data_uri or ""

    @staticmethod
    def _call_vlm_sync(
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str,
        ref_url: str,
    ) -> str:
        """同步调用 OpenAI 兼容接口，返回 message.content 字符串。

        用一个显式直连的 httpx.Client（trust_env=False），避免 uvicorn 进程
        误继承 macOS 系统代理或残留的 HTTP(S)_PROXY 变量。
        """
        import httpx
        from openai import OpenAI

        proxy_env = {
            k: os.environ.get(k, "")
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                     "http_proxy", "https_proxy", "all_proxy", "NO_PROXY", "no_proxy")
            if os.environ.get(k)
        }
        if proxy_env:
            logger.info(
                "[CompetitorDeconstructor] detected proxy env in process: %s — 将以直连覆盖",
                proxy_env,
            )

        http_client = httpx.Client(
            trust_env=False,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
        )
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": ref_url}},
                    {"type": "text", "text": _USER_HINT},
                ],
            },
        ]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        if provider == "openrouter":
            kwargs["extra_body"] = {"provider": {"allow_fallbacks": True}}

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            msg = str(exc)
            if "response_format" in msg or "json_object" in msg:
                kwargs.pop("response_format", None)
                resp = client.chat.completions.create(**kwargs)
            else:
                raise

        choices = getattr(resp, "choices", []) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", "") if message is not None else ""
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif isinstance(part, str):
                    parts.append(part)
            return "\n".join(parts).strip()
        return (content or "").strip()

    @staticmethod
    def _safe_json(text: str) -> dict:
        if not text:
            return {}
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _empty_skeleton(*, reason: str = "") -> dict:
        empty_group = lambda keys: {k: "" for k in keys}
        return {
            "composition_color": empty_group([
                "主体物位置", "构图方式", "层次关系", "主色调",
                "辅助色", "色彩对比", "色彩情绪", "产品占比",
            ]),
            "display_copy": empty_group([
                "展示角度", "展示数量", "细节呈现", "标题文字",
                "促销信息", "卖点文案", "文字位置", "文字占比",
            ]),
            "background_mood": empty_group([
                "背景类型", "背景颜色", "简洁程度", "氛围营造",
                "装饰元素", "图标标识", "边框修饰", "特效处理",
            ]),
            "scene_quality": empty_group([
                "使用场景", "人物元素", "生活化元素", "场景道具",
                "图片清晰度", "光影处理", "精致程度", "专业度",
            ]),
            "summary": "",
            "borrow_ideas": [],
            "avoid_ideas": [],
            "note": f"degraded: {reason}",
        }


_instance: CompetitorDeconstructor | None = None


def get_competitor_deconstructor() -> CompetitorDeconstructor:
    global _instance
    if _instance is None:
        _instance = CompetitorDeconstructor()
    return _instance
