"""LLM 回傳的 JSON 解析驗證與自動修復。"""

import json
import logging
import re

from yt_finance_analyzer.models import (
    DailyTrendAnalysis,
    SchemaValidationError,
    VideoAnalysis,
    WeeklyTrendAnalysis,
)

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> str:
    """從 LLM 回應中提取 JSON 字串，處理常見格式問題。"""
    text = raw.strip()

    # 移除 markdown code block 標記
    if text.startswith("```"):
        # 移除開頭的 ```json 或 ```
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # 移除結尾的 ```
        text = re.sub(r"\n?```\s*$", "", text)

    # 嘗試找到 JSON 物件的起始和結束
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    return text


def validate_analysis(raw_json: str) -> VideoAnalysis:
    """解析並驗證單支影片分析結果。

    Args:
        raw_json: LLM 回傳的 JSON 字串。

    Returns:
        VideoAnalysis 物件。

    Raises:
        SchemaValidationError: JSON 格式或 schema 驗證失敗。
    """
    try:
        cleaned = _extract_json(raw_json)
        data = json.loads(cleaned)
        return VideoAnalysis.model_validate(data)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"VideoAnalysis JSON 解析失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc
    except Exception as exc:
        raise SchemaValidationError(
            f"VideoAnalysis schema 驗證失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc


def validate_trend(raw_json: str) -> DailyTrendAnalysis:
    """解析並驗證每日趨勢分析結果。

    Args:
        raw_json: LLM 回傳的 JSON 字串。

    Returns:
        DailyTrendAnalysis 物件。

    Raises:
        SchemaValidationError: JSON 格式或 schema 驗證失敗。
    """
    try:
        cleaned = _extract_json(raw_json)
        data = json.loads(cleaned)
        return DailyTrendAnalysis.model_validate(data)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"DailyTrendAnalysis JSON 解析失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc
    except Exception as exc:
        raise SchemaValidationError(
            f"DailyTrendAnalysis schema 驗證失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc


def validate_weekly_trend(raw_json: str) -> WeeklyTrendAnalysis:
    """解析並驗證每週趨勢分析結果。

    Args:
        raw_json: LLM 回傳的 JSON 字串。

    Returns:
        WeeklyTrendAnalysis 物件。

    Raises:
        SchemaValidationError: JSON 格式或 schema 驗證失敗。
    """
    try:
        cleaned = _extract_json(raw_json)
        data = json.loads(cleaned)
        return WeeklyTrendAnalysis.model_validate(data)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"WeeklyTrendAnalysis JSON 解析失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc
    except Exception as exc:
        raise SchemaValidationError(
            f"WeeklyTrendAnalysis schema 驗證失敗: {exc}\n原始回應前 500 字: {raw_json[:500]}"
        ) from exc
