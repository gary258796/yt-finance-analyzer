"""單支影片 LLM 分析服務。"""

import json
import logging
import time
from pathlib import Path

from yt_finance_analyzer.analysis.base import LLMProvider
from yt_finance_analyzer.analysis.prompts import (
    PRELIMINARY_SUMMARY_PROMPT,
    PRELIMINARY_SUMMARY_SYSTEM_PROMPT,
    VIDEO_ANALYSIS_PROMPT,
    VIDEO_ANALYSIS_SYSTEM_PROMPT,
)
from yt_finance_analyzer.analysis.schema_validator import validate_analysis
from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import AnalysisError, TranscriptResult, VideoAnalysis, VideoMetadata
from yt_finance_analyzer.utils.text_processing import chunk_text

logger = logging.getLogger(__name__)


class VideoAnalyzerService:
    """單支影片的 LLM 分析服務。"""

    def __init__(self, settings: Settings, llm_provider: LLMProvider) -> None:
        self._settings = settings
        self._llm = llm_provider

    def analyze_video(
        self, metadata: VideoMetadata, transcript: TranscriptResult
    ) -> VideoAnalysis:
        """分析單支影片，支援長文 chunking。

        Args:
            metadata: 影片 metadata。
            transcript: 逐字稿。

        Returns:
            VideoAnalysis 分析結果。

        Raises:
            AnalysisError: 分析失敗。
        """
        video_id = metadata.video_id
        start_time = time.time()
        logger.info("開始分析影片: %s (%s)", video_id, metadata.title)

        # 檢查快取
        cached = self._load_cached(video_id)
        if cached:
            logger.info("使用快取的分析結果: %s", video_id)
            return cached

        text = transcript.cleaned_text
        max_chars = self._settings.max_transcript_chars

        if len(text) <= max_chars:
            analysis = self._analyze_full(metadata, text)
        else:
            logger.info(
                "逐字稿過長 (%d > %d)，使用 chunking 分析",
                len(text),
                max_chars,
            )
            analysis = self._analyze_chunked(metadata, text, max_chars)

        # 儲存結果
        self._save_result(video_id, analysis)

        elapsed = time.time() - start_time
        logger.info("影片分析完成: %s (耗時 %.1f 秒)", video_id, elapsed)
        return analysis

    def _analyze_full(self, metadata: VideoMetadata, text: str) -> VideoAnalysis:
        """直接分析完整逐字稿。"""
        prompt = VIDEO_ANALYSIS_PROMPT.format(
            video_id=metadata.video_id,
            title=metadata.title,
            channel_name=metadata.channel_name,
            published_at=metadata.published_at.isoformat(),
            url=metadata.url,
            description=metadata.description[:500],
            transcript=text,
        )

        raw_response = self._llm.analyze(prompt, VIDEO_ANALYSIS_SYSTEM_PROMPT)
        return validate_analysis(raw_response)

    def _analyze_chunked(
        self, metadata: VideoMetadata, text: str, max_chars: int
    ) -> VideoAnalysis:
        """將長逐字稿分段摘要後再合併分析。"""
        chunks = chunk_text(text, max_chars=max_chars, overlap=500)
        logger.info("逐字稿切割為 %d 段", len(chunks))

        # 對每個 chunk 做初步摘要
        summaries: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            logger.info("分析片段 %d/%d", i, len(chunks))
            prompt = PRELIMINARY_SUMMARY_PROMPT.format(
                chunk_index=i,
                total_chunks=len(chunks),
                title=metadata.title,
                channel_name=metadata.channel_name,
                chunk_text=chunk,
            )
            summary = self._llm.analyze(prompt, PRELIMINARY_SUMMARY_SYSTEM_PROMPT)
            summaries.append(summary)

        # 合併所有摘要，再做完整分析
        merged_text = "\n\n---\n\n".join(
            f"【片段 {i+1}/{len(summaries)} 摘要】\n{s}"
            for i, s in enumerate(summaries)
        )

        logger.info("合併 %d 段摘要進行完整分析", len(summaries))
        return self._analyze_full(metadata, merged_text)

    def _load_cached(self, video_id: str) -> VideoAnalysis | None:
        """載入快取的分析結果。"""
        cache_path = self._settings.analysis_dir / f"{video_id}.json"
        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return VideoAnalysis.model_validate(data)
        except Exception as exc:
            logger.warning("載入快取失敗 %s: %s", video_id, exc)
            return None

    def _save_result(self, video_id: str, analysis: VideoAnalysis) -> None:
        """儲存分析結果為 JSON。"""
        output_dir = self._settings.analysis_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_id}.json"

        output_path.write_text(
            analysis.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("分析結果已儲存: %s", output_path)
