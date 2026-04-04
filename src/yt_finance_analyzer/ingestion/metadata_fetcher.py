"""透過 YouTube Data API v3 取得影片完整 metadata。"""

import logging
import re
from datetime import datetime

from googleapiclient.discovery import build

from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import VideoFetchError, VideoMetadata
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)


def _parse_duration(duration_str: str) -> int:
    """將 ISO 8601 duration（如 PT1H2M3S）轉為秒數。"""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


class MetadataFetcher:
    """取得 YouTube 影片的完整 metadata。"""

    def __init__(self, settings: Settings) -> None:
        self._youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)

    @retry(max_retries=3, delay=2.0, backoff_factor=2.0, exceptions=(Exception,))
    def fetch_metadata(self, video_id: str, language: str | None = None) -> VideoMetadata:
        """取得單支影片的完整 metadata。

        Args:
            video_id: YouTube 影片 ID。
            language: 影片語言（從頻道設定帶入）。

        Returns:
            VideoMetadata 物件。

        Raises:
            VideoFetchError: 取得 metadata 失敗。
        """
        logger.info("取得影片 metadata: %s", video_id)

        try:
            response = self._youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id,
            ).execute()
        except Exception as exc:
            raise VideoFetchError(f"取得影片 {video_id} metadata 失敗: {exc}") from exc

        items = response.get("items", [])
        if not items:
            raise VideoFetchError(f"找不到影片: {video_id}")

        item = items[0]
        snippet = item["snippet"]
        content_details = item.get("contentDetails", {})

        duration_seconds = None
        if "duration" in content_details:
            duration_seconds = _parse_duration(content_details["duration"])

        # 使用影片的 defaultAudioLanguage 或 defaultLanguage，若都沒有則用傳入的 language
        video_language = (
            snippet.get("defaultAudioLanguage")
            or snippet.get("defaultLanguage")
            or language
        )

        metadata = VideoMetadata(
            video_id=video_id,
            title=snippet["title"],
            channel_id=snippet["channelId"],
            channel_name=snippet.get("channelTitle", ""),
            published_at=datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            ),
            url=f"https://www.youtube.com/watch?v={video_id}",
            description=snippet.get("description", ""),
            duration_seconds=duration_seconds,
            language=video_language,
        )

        logger.info(
            "影片 %s metadata 取得完成: %s (%s 秒)",
            video_id,
            metadata.title,
            duration_seconds,
        )
        return metadata
