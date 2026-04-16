"""video_processor — 视频处理管线。

Phase 3 能力：
- ffmpeg 切片（前 3 秒提取）
- whisper 语音转写
- 钩子类型自动识别（基于文本分析 + LLM）
- 元数据提取

MVP 阶段：ffmpeg + whisper 为外部依赖可选；
缺失时降级为仅处理元数据。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

_FFMPEG_CMD = os.environ.get("FFMPEG_PATH", "ffmpeg")
_FFPROBE_CMD = os.environ.get("FFPROBE_PATH", "ffprobe")


@dataclass
class VideoMetadata:
    """视频元数据。"""

    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    file_size_bytes: int = 0
    has_audio: bool = False


@dataclass
class TranscriptSegment:
    """转写片段。"""

    start: float = 0.0
    end: float = 0.0
    text: str = ""


@dataclass
class HookAnalysis:
    """钩子分析结果。"""

    detected_hook_type: str = ""
    conflict_type: str = ""
    opening_text: str = ""
    confidence: float = 0.0
    visual_notes: str = ""


@dataclass
class VideoProcessResult:
    """完整的视频处理结果。"""

    video_id: str = ""
    source_path: str = ""
    clip_path: str = ""
    metadata: VideoMetadata | None = None
    transcript: list[TranscriptSegment] = field(default_factory=list)
    full_transcript_text: str = ""
    hook_analysis: HookAnalysis | None = None
    error: str = ""
    processing_ms: int = 0


class VideoProcessor:
    """视频处理管线——切片 + 转写 + 钩子识别。"""

    def __init__(
        self,
        output_dir: str | Path | None = None,
        clip_duration: float = 3.0,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "growth_lab_clips"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.clip_duration = clip_duration
        self._ffmpeg_available: bool | None = None
        self._whisper_available: bool | None = None

    # ── 公共 API ──────────────────────────────────────────────

    async def process_video(
        self,
        video_path: str | Path,
        *,
        extract_clip: bool = True,
        transcribe: bool = True,
        analyze_hook: bool = True,
    ) -> VideoProcessResult:
        """完整处理管线：元数据 -> 切片 -> 转写 -> 钩子识别。"""
        start = time.monotonic()
        video_path = Path(video_path)
        video_id = uuid.uuid4().hex[:16]

        result = VideoProcessResult(
            video_id=video_id,
            source_path=str(video_path),
        )

        if not video_path.exists():
            result.error = f"视频文件不存在: {video_path}"
            return result

        result.metadata = self._extract_metadata(video_path)

        if extract_clip and self._check_ffmpeg():
            result.clip_path = self._extract_clip(video_path, video_id)

        if transcribe:
            target = result.clip_path or str(video_path)
            segments = await self._transcribe(target)
            result.transcript = segments
            result.full_transcript_text = " ".join(s.text for s in segments)

        if analyze_hook and result.full_transcript_text:
            result.hook_analysis = await self._analyze_hook(result.full_transcript_text)

        result.processing_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "视频处理完成: id=%s duration=%.1fs transcript_len=%d hook=%s elapsed=%dms",
            video_id,
            result.metadata.duration_seconds if result.metadata else 0,
            len(result.full_transcript_text),
            result.hook_analysis.detected_hook_type if result.hook_analysis else "N/A",
            result.processing_ms,
        )
        return result

    # ── ffmpeg 元数据 ────────────────────────────────────────

    def _extract_metadata(self, video_path: Path) -> VideoMetadata:
        """用 ffprobe 提取视频元数据。"""
        if not self._check_ffmpeg():
            return VideoMetadata(file_size_bytes=video_path.stat().st_size)

        try:
            cmd = [
                _FFPROBE_CMD, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(video_path),
            ]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if out.returncode != 0:
                return VideoMetadata(file_size_bytes=video_path.stat().st_size)

            data = json.loads(out.stdout)
            fmt = data.get("format", {})
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {},
            )
            audio_stream = any(
                s.get("codec_type") == "audio" for s in data.get("streams", [])
            )

            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) else 0
            except (ValueError, ZeroDivisionError):
                fps = 0

            return VideoMetadata(
                duration_seconds=float(fmt.get("duration", 0)),
                width=int(video_stream.get("width", 0)),
                height=int(video_stream.get("height", 0)),
                fps=round(fps, 2),
                codec=video_stream.get("codec_name", ""),
                file_size_bytes=int(fmt.get("size", video_path.stat().st_size)),
                has_audio=audio_stream,
            )
        except Exception as e:
            logger.warning("ffprobe 失败: %s", e)
            return VideoMetadata(file_size_bytes=video_path.stat().st_size)

    # ── ffmpeg 切片 ──────────────────────────────────────────

    def _extract_clip(self, video_path: Path, video_id: str) -> str:
        """提取前 N 秒视频片段。"""
        output_path = self.output_dir / f"{video_id}_first{self.clip_duration:.0f}s.mp4"
        try:
            cmd = [
                _FFMPEG_CMD, "-y",
                "-i", str(video_path),
                "-t", str(self.clip_duration),
                "-c", "copy",
                str(output_path),
            ]
            subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            logger.info("视频切片完成: %s", output_path)
            return str(output_path)
        except Exception as e:
            logger.warning("视频切片失败: %s", e)
            return ""

    # ── Whisper 转写 ─────────────────────────────────────────

    async def _transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        """用 whisper 做语音转写。"""
        if not audio_path:
            return []

        if self._check_whisper():
            return self._whisper_transcribe(audio_path)

        logger.info("whisper 不可用，跳过转写")
        return []

    def _whisper_transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        """调用 openai-whisper 转写。"""
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="zh")
            segments = []
            for seg in result.get("segments", []):
                segments.append(TranscriptSegment(
                    start=seg.get("start", 0),
                    end=seg.get("end", 0),
                    text=seg.get("text", "").strip(),
                ))
            return segments
        except Exception as e:
            logger.warning("whisper 转写失败: %s", e)
            return []

    # ── 钩子分析 ─────────────────────────────────────────────

    async def _analyze_hook(self, transcript_text: str) -> HookAnalysis:
        """分析前 3 秒文本的钩子类型。"""
        llm_result = await self._try_llm_analysis(transcript_text)
        if llm_result:
            return llm_result

        return self._rule_based_analysis(transcript_text)

    async def _try_llm_analysis(self, text: str) -> HookAnalysis | None:
        try:
            from apps.content_planning.adapters.llm_router import LLMMessage, llm_router
        except ImportError:
            return None

        prompt = (
            f"分析以下短视频前3秒口播文本的钩子类型。\n\n文本: \"{text}\"\n\n"
            "输出严格 JSON:\n"
            '{"hook_type": "question|shock|contrast|pain_point|benefit|curiosity|authority|social_proof|urgency|storytelling", '
            '"conflict_type": "冲突描述", "confidence": 0.0-1.0}'
        )
        try:
            data = llm_router.chat_json(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=200,
            )
            if data and data.get("hook_type"):
                return HookAnalysis(
                    detected_hook_type=data["hook_type"],
                    conflict_type=data.get("conflict_type", ""),
                    opening_text=text[:50],
                    confidence=float(data.get("confidence", 0.5)),
                )
        except Exception:
            logger.debug("LLM 钩子分析失败", exc_info=True)
        return None

    @staticmethod
    def _rule_based_analysis(text: str) -> HookAnalysis:
        """规则匹配钩子类型。"""
        text_lower = text.lower()

        if "?" in text or "？" in text or any(w in text_lower for w in ["为什么", "怎么", "吗", "你知道"]):
            return HookAnalysis(detected_hook_type="question", opening_text=text[:50], confidence=0.6)
        if any(w in text_lower for w in ["别再", "千万别", "踩坑", "后悔", "亏"]):
            return HookAnalysis(detected_hook_type="pain_point", opening_text=text[:50], confidence=0.6)
        if any(w in text_lower for w in ["居然", "没想到", "震惊", "天呐"]):
            return HookAnalysis(detected_hook_type="shock", opening_text=text[:50], confidence=0.5)
        if any(w in text_lower for w in ["对比", "区别", "同样", "差距"]):
            return HookAnalysis(detected_hook_type="contrast", opening_text=text[:50], confidence=0.5)
        if any(w in text_lower for w in ["省", "赚", "免费", "优惠", "值"]):
            return HookAnalysis(detected_hook_type="benefit", opening_text=text[:50], confidence=0.5)
        return HookAnalysis(detected_hook_type="curiosity", opening_text=text[:50], confidence=0.3)

    # ── 工具检测 ─────────────────────────────────────────────

    def _check_ffmpeg(self) -> bool:
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available
        try:
            subprocess.run([_FFMPEG_CMD, "-version"], capture_output=True, timeout=5)
            self._ffmpeg_available = True
        except Exception:
            self._ffmpeg_available = False
            logger.info("ffmpeg 不可用，视频切片功能将跳过")
        return self._ffmpeg_available

    def _check_whisper(self) -> bool:
        if self._whisper_available is not None:
            return self._whisper_available
        try:
            import whisper  # noqa: F401
            self._whisper_available = True
        except ImportError:
            self._whisper_available = False
            logger.info("whisper 不可用，语音转写功能将跳过")
        return self._whisper_available
