"""每日與每週趨勢彙整分析服務。"""

import json
import logging
import time
from pathlib import Path

from yt_finance_analyzer.analysis.base import LLMProvider
from yt_finance_analyzer.analysis.prompts import (
    DAILY_TREND_PROMPT,
    DAILY_TREND_SYSTEM_PROMPT,
    WEEKLY_TREND_PROMPT,
    WEEKLY_TREND_SYSTEM_PROMPT,
)
from yt_finance_analyzer.analysis.schema_validator import validate_trend, validate_weekly_trend
from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import DailyTrendAnalysis, VideoAnalysis, WeeklyTrendAnalysis

logger = logging.getLogger(__name__)


class TrendAnalyzerService:
    """每日與每週趨勢彙整分析。"""

    def __init__(self, settings: Settings, llm_provider: LLMProvider) -> None:
        self._settings = settings
        self._llm = llm_provider

    def analyze_daily_trend(
        self, analyses: list[VideoAnalysis], date: str
    ) -> DailyTrendAnalysis:
        """彙整當天所有影片分析結果，產出每日趨勢。

        Args:
            analyses: 當天所有影片的分析結果。
            date: 日期字串（YYYY-MM-DD）。

        Returns:
            DailyTrendAnalysis 每日趨勢分析。
        """
        start_time = time.time()
        logger.info("開始每日趨勢分析: %s (%d 支影片)", date, len(analyses))

        # 將所有分析結果序列化為 JSON
        analyses_data = [
            a.model_dump(mode="json") for a in analyses
        ]
        analyses_json = json.dumps(analyses_data, ensure_ascii=False, indent=2)

        prompt = DAILY_TREND_PROMPT.format(
            date=date,
            total_videos=len(analyses),
            analyses_json=analyses_json,
        )

        raw_response = self._llm.analyze(prompt, DAILY_TREND_SYSTEM_PROMPT)
        trend = validate_trend(raw_response)

        # 儲存結果
        self._save_daily_trend(date, trend)

        elapsed = time.time() - start_time
        logger.info("每日趨勢分析完成: %s (耗時 %.1f 秒)", date, elapsed)
        return trend

    def analyze_weekly_trend(
        self, analyses: list[VideoAnalysis], week_start: str, week_end: str
    ) -> WeeklyTrendAnalysis:
        """彙整當週所有影片分析結果，產出每週趨勢。

        Args:
            analyses: 當週所有影片的分析結果。
            week_start: 週起始日（YYYY-MM-DD）。
            week_end: 週結束日（YYYY-MM-DD）。

        Returns:
            WeeklyTrendAnalysis 每週趨勢分析。
        """
        start_time = time.time()
        logger.info(
            "開始每週趨勢分析: %s ~ %s (%d 支影片)",
            week_start,
            week_end,
            len(analyses),
        )

        analyses_data = [
            a.model_dump(mode="json") for a in analyses
        ]
        analyses_json = json.dumps(analyses_data, ensure_ascii=False, indent=2)

        prompt = WEEKLY_TREND_PROMPT.format(
            week_start=week_start,
            week_end=week_end,
            total_videos=len(analyses),
            analyses_json=analyses_json,
        )

        raw_response = self._llm.analyze(prompt, WEEKLY_TREND_SYSTEM_PROMPT)
        trend = validate_weekly_trend(raw_response)

        # 儲存結果
        self._save_weekly_trend(week_start, week_end, trend)

        elapsed = time.time() - start_time
        logger.info(
            "每週趨勢分析完成: %s ~ %s (耗時 %.1f 秒)",
            week_start,
            week_end,
            elapsed,
        )
        return trend

    def _save_daily_trend(self, date: str, trend: DailyTrendAnalysis) -> None:
        """儲存每日趨勢分析結果。"""
        output_dir = self._settings.analysis_dir / "trends"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"daily_{date}.json"

        output_path.write_text(
            trend.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("每日趨勢已儲存: %s", output_path)

    def _save_weekly_trend(
        self, week_start: str, week_end: str, trend: WeeklyTrendAnalysis
    ) -> None:
        """儲存每週趨勢分析結果。"""
        output_dir = self._settings.analysis_dir / "trends"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"weekly_{week_start}_{week_end}.json"

        output_path.write_text(
            trend.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("每週趨勢已儲存: %s", output_path)
