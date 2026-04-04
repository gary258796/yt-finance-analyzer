"""OpenAI Whisper API 語音轉文字實作。"""

import logging
import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI

from yt_finance_analyzer.models import TranscriptionError
from yt_finance_analyzer.transcription.base import STTProvider
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)

# Whisper API 檔案大小上限（25MB）
_MAX_FILE_SIZE = 25 * 1024 * 1024

# 切割時每段的目標時長（秒），保守估計以確保不超過 25MB
_SEGMENT_DURATION = 600  # 10 分鐘


class WhisperSTTProvider(STTProvider):
    """使用 OpenAI Whisper API 進行語音轉文字。"""

    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def transcribe(self, audio_path: Path, language: str) -> str:
        """將音訊檔轉成文字。

        若檔案超過 25MB，自動切割後逐段轉錄再合併。

        Args:
            audio_path: 音訊檔案路徑。
            language: 語言代碼（如 zh, en）。

        Returns:
            轉錄後的完整文字。

        Raises:
            TranscriptionError: 轉錄失敗。
        """
        if not audio_path.exists():
            raise TranscriptionError(f"音訊檔案不存在: {audio_path}")

        file_size = audio_path.stat().st_size
        # Whisper API 的語言代碼只取前兩碼
        lang_code = language.split("-")[0]

        logger.info(
            "開始 Whisper 轉錄: %s (%.1f MB, 語言: %s)",
            audio_path.name,
            file_size / 1024 / 1024,
            lang_code,
        )

        if file_size <= _MAX_FILE_SIZE:
            return self._transcribe_single(audio_path, lang_code)

        # 大檔案：切割後逐段轉錄
        logger.info("檔案超過 25MB，進行切割轉錄")
        return self._transcribe_chunked(audio_path, lang_code)

    @retry(max_retries=3, delay=5.0, backoff_factor=2.0, exceptions=(Exception,))
    def _transcribe_single(self, audio_path: Path, language: str) -> str:
        """轉錄單一音訊檔案。"""
        try:
            with open(audio_path, "rb") as f:
                response = self._client.audio.transcriptions.create(
                    model=self._model,
                    file=f,
                    language=language,
                    response_format="text",
                )
            text = str(response).strip()
            logger.info("轉錄完成: %s (%d 字元)", audio_path.name, len(text))
            return text
        except Exception as exc:
            raise TranscriptionError(
                f"Whisper 轉錄失敗 {audio_path.name}: {exc}"
            ) from exc

    def _transcribe_chunked(self, audio_path: Path, language: str) -> str:
        """切割大檔案後逐段轉錄再合併。"""
        segments = self._split_audio(audio_path)
        if not segments:
            raise TranscriptionError(f"音訊切割失敗: {audio_path}")

        texts: list[str] = []
        try:
            for i, segment_path in enumerate(segments, 1):
                logger.info("轉錄片段 %d/%d: %s", i, len(segments), segment_path.name)
                text = self._transcribe_single(segment_path, language)
                if text:
                    texts.append(text)
        finally:
            # 清理暫存切割檔案
            for seg in segments:
                seg.unlink(missing_ok=True)

        result = "\n".join(texts)
        logger.info("切割轉錄完成: 共 %d 段, %d 字元", len(texts), len(result))
        return result

    def _split_audio(self, audio_path: Path) -> list[Path]:
        """使用 ffmpeg 將音訊切割為多個片段。"""
        tmp_dir = Path(tempfile.mkdtemp(prefix="whisper_split_"))
        output_pattern = str(tmp_dir / f"segment_%03d{audio_path.suffix}")

        cmd = [
            "ffmpeg", "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", str(_SEGMENT_DURATION),
            "-c", "copy",
            "-y",
            output_pattern,
        ]

        logger.info("切割音訊: %s (每段 %d 秒)", audio_path.name, _SEGMENT_DURATION)

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
        except FileNotFoundError:
            raise TranscriptionError(
                "ffmpeg 未安裝，無法切割大型音訊檔案。請安裝 ffmpeg。"
            )
        except subprocess.CalledProcessError as exc:
            raise TranscriptionError(
                f"ffmpeg 切割失敗: {exc.stderr}"
            ) from exc

        segments = sorted(tmp_dir.glob(f"segment_*{audio_path.suffix}"))
        logger.info("音訊切割完成: %d 個片段", len(segments))
        return segments
