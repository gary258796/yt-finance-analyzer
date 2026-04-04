"""逐字稿前處理與清洗。"""

import logging
from typing import Literal

from yt_finance_analyzer.models import TranscriptResult
from yt_finance_analyzer.utils.text_processing import clean_transcript

logger = logging.getLogger(__name__)


def process_transcript(
    video_id: str,
    raw_text: str,
    source: Literal["subtitle", "whisper"],
    language: str,
) -> TranscriptResult:
    """處理原始逐字稿：清洗文字、計算統計。

    Args:
        video_id: 影片 ID。
        raw_text: 原始逐字稿文字。
        source: 來源標記（subtitle 或 whisper）。
        language: 語言代碼。

    Returns:
        TranscriptResult 處理結果。
    """
    cleaned = clean_transcript(raw_text)

    char_count = len(cleaned)
    # 中文以字元計數，英文以空格分詞
    if language.startswith("zh"):
        word_count = char_count
    else:
        word_count = len(cleaned.split())

    logger.info(
        "逐字稿處理完成: %s (來源: %s, %d 字元, %d 詞)",
        video_id,
        source,
        char_count,
        word_count,
    )

    return TranscriptResult(
        video_id=video_id,
        source=source,
        raw_text=raw_text,
        cleaned_text=cleaned,
        language=language,
        char_count=char_count,
        word_count=word_count,
    )
