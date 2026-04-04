"""所有 Pydantic data models 與自訂 exception classes。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class VideoMetadata(BaseModel):
    """YouTube 影片 metadata。"""

    video_id: str
    title: str
    channel_id: str
    channel_name: str
    published_at: datetime
    url: str
    description: str
    duration_seconds: int | None = None
    language: str | None = None


class TranscriptResult(BaseModel):
    """逐字稿處理結果。"""

    video_id: str
    source: Literal["subtitle", "whisper"]
    raw_text: str
    cleaned_text: str
    language: str
    char_count: int
    word_count: int


class VideoAnalysis(BaseModel):
    """單支影片 LLM 分析結果 — 核心 schema。"""

    video_id: str
    title: str
    channel_name: str
    published_at: datetime
    url: str
    summary_short: str
    summary_long: str
    bullet_points: list[str]
    keywords: list[str]
    topics: list[str]
    industries: list[str]
    mentioned_tickers_or_assets: list[str]
    macro_factors: list[str]
    speaker_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    confidence_level: Literal["high", "medium", "low"]
    claims_explicit: list[str]
    inferred_insights: list[str]
    bullish_points: list[str]
    bearish_points: list[str]
    actionable_watchlist: list[str]
    risk_warnings: list[str]
    notable_quotes: list[str]


class DailyTrendAnalysis(BaseModel):
    """每日趨勢彙整。"""

    date: str
    total_videos_analyzed: int
    common_topics: list[str]
    top_industries: list[str]
    top_assets: list[str]
    overall_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    sentiment_breakdown: dict[str, int]
    high_frequency_keywords: list[str]
    strong_conviction_items: list[str]
    recommended_watchlist: list[str]
    risk_summary: list[str]
    daily_narrative: str


class WeeklyTrendAnalysis(BaseModel):
    """每週趨勢彙整。"""

    week_start: str
    week_end: str
    total_videos_analyzed: int
    common_topics: list[str]
    top_industries: list[str]
    top_assets: list[str]
    overall_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    sentiment_trend: str
    high_frequency_keywords: list[str]
    strong_conviction_items: list[str]
    recommended_watchlist: list[str]
    risk_summary: list[str]
    weekly_narrative: str


class ProcessingStatus(BaseModel):
    """影片處理狀態。"""

    video_id: str
    status: Literal["pending", "transcript_done", "analysis_done", "reported", "failed"]
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_seconds: float | None = None


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class VideoFetchError(Exception):
    """影片抓取失敗。"""


class TranscriptionError(Exception):
    """語音轉文字失敗。"""


class AnalysisError(Exception):
    """LLM 分析失敗。"""


class SchemaValidationError(Exception):
    """JSON schema 驗證失敗。"""


class ReportGenerationError(Exception):
    """報告產生失敗。"""


class EmailSendError(Exception):
    """Email 寄送失敗。"""
