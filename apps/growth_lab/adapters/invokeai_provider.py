"""InvokeAI Provider — 本地 GPU 推理 adapter。

通过 InvokeAI REST API 调用本地部署的 Stable Diffusion / FLUX 服务，
用于精细控制的主图裂变场景（ControlNet + IP-Adapter）。

MVP 阶段为 mock 实现；真正接入需要 InvokeAI 本地服务运行。
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VariantResult:
    """生成结果。"""

    variant_id: str = ""
    image_url: str = ""
    provider: str = "invokeai"
    elapsed_ms: int = 0
    metadata: dict[str, Any] | None = None
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.image_url) and not self.error


class InvokeAIProvider:
    """InvokeAI 本地推理 adapter。

    与现有 ImageGeneratorService 的 API 通道并列使用：
    - ImageGeneratorService: DashScope / OpenRouter 云端生成
    - InvokeAIProvider: 本地 GPU 推理（SD/FLUX/ControlNet/LoRA）

    MVP 阶段：mock 实现。
    Phase 2：通过 InvokeAI REST API (/api/v1/queue/enqueue_batch) 接入。
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url or os.environ.get(
            "INVOKEAI_BASE_URL", "http://localhost:9090",
        )
        self.timeout_seconds = timeout_seconds
        self._available: bool | None = None

    async def is_available(self) -> bool:
        """检测 InvokeAI 服务是否在线。"""
        if self._available is not None:
            return self._available
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/v1/app/version")
                self._available = resp.status_code == 200
        except Exception:
            self._available = False
        logger.info("InvokeAI 可用性检测: %s (%s)", self._available, self.base_url)
        return self._available

    async def generate_variant(
        self,
        spec: dict[str, Any],
    ) -> VariantResult:
        """从 ImageVariantSpec dict 生成单张图片。

        真正接入时将构建 InvokeAI Graph JSON，调用 /api/v1/queue/enqueue_batch
        并轮询结果。MVP 阶段返回 mock 数据。
        """
        variant_id = spec.get("spec_id", uuid.uuid4().hex[:12])
        start = time.monotonic()

        if await self.is_available():
            return await self._invoke_real(spec, variant_id, start)

        return self._mock_generate(spec, variant_id, start)

    async def generate_batch(
        self,
        specs: list[dict[str, Any]],
    ) -> list[VariantResult]:
        """批量生成。MVP 阶段串行调用 generate_variant。"""
        results = []
        for spec in specs:
            r = await self.generate_variant(spec)
            results.append(r)
        return results

    # ── Phase 2: 真正的 InvokeAI API 调用 ──

    async def _invoke_real(
        self,
        spec: dict[str, Any],
        variant_id: str,
        start: float,
    ) -> VariantResult:
        """真正的 InvokeAI API 调用（Phase 2 实现）。"""
        graph = self._build_graph(spec)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/queue/default/enqueue_batch",
                    json={"batch": {"graph": graph, "runs": 1}},
                )
                if resp.status_code != 200:
                    return VariantResult(
                        variant_id=variant_id,
                        error=f"InvokeAI API error: {resp.status_code}",
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                    )
                data = resp.json()
                batch_id = data.get("batch_id", "")

                image_url = await self._poll_result(client, batch_id)
                elapsed = int((time.monotonic() - start) * 1000)
                return VariantResult(
                    variant_id=variant_id,
                    image_url=image_url,
                    provider="invokeai",
                    elapsed_ms=elapsed,
                    metadata={"batch_id": batch_id, "graph_nodes": list(graph.get("nodes", {}).keys())},
                )
        except Exception as e:
            logger.warning("InvokeAI 调用失败: %s", e)
            return self._mock_generate(spec, variant_id, start)

    async def _poll_result(
        self,
        client: Any,
        batch_id: str,
        max_polls: int = 60,
        poll_interval: float = 2.0,
    ) -> str:
        """轮询 InvokeAI 队列获取结果图片 URL。"""
        import asyncio
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                resp = await client.get(
                    f"{self.base_url}/api/v1/queue/default/status",
                )
                if resp.status_code == 200:
                    status = resp.json()
                    if status.get("queue", {}).get("completed", 0) > 0:
                        return f"{self.base_url}/api/v1/images/latest"
            except Exception:
                continue
        return ""

    def _build_graph(self, spec: dict[str, Any]) -> dict:
        """将 ImageVariantSpec 转为 InvokeAI Graph JSON（骨架）。

        Phase 2 将实现完整的 node 拓扑：
        - TextToImage / ImageToImage
        - ControlNet (构图控制)
        - IP-Adapter (参考图风格迁移)
        - Upscale
        """
        prompt = spec.get("base_prompt", "")
        negative = spec.get("negative_prompt", "")
        size = spec.get("size", "1024*1024")
        w, h = (int(x) for x in size.split("*")) if "*" in size else (1024, 1024)

        return {
            "nodes": {
                "text_to_image": {
                    "type": "txt2img",
                    "prompt": prompt,
                    "negative_prompt": negative,
                    "width": w,
                    "height": h,
                    "steps": 30,
                    "cfg_scale": 7.5,
                    "scheduler": "euler",
                }
            },
            "edges": [],
        }

    # ── Mock ──

    @staticmethod
    def _mock_generate(
        spec: dict[str, Any],
        variant_id: str,
        start: float,
    ) -> VariantResult:
        """MVP mock：返回占位结果。"""
        elapsed = int((time.monotonic() - start) * 1000)
        return VariantResult(
            variant_id=variant_id,
            image_url=f"https://mock-invokeai.example.com/generated/{variant_id}.png",
            provider="invokeai_mock",
            elapsed_ms=elapsed,
            metadata={"mock": True, "prompt": spec.get("base_prompt", "")[:100]},
        )
