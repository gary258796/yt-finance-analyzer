"""檢查 YouTube 頻道是否有新影片，支援透過 handle 解析 channel_id。"""

import logging
from datetime import datetime

from googleapiclient.discovery import build

from yt_finance_analyzer.config import ChannelConfig, Settings
from yt_finance_analyzer.models import VideoFetchError, VideoMetadata
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)


class ChannelChecker:
    """透過 YouTube Data API v3 檢查頻道新影片。"""

    def __init__(self, settings: Settings) -> None:
        self._youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)

    def resolve_channel_id(self, handle: str) -> str:
        """透過 handle（如 @yutinghaofinance）解析出 channel_id。

        Args:
            handle: YouTube 頻道 handle，需以 @ 開頭。

        Returns:
            channel_id（UC... 格式）。

        Raises:
            VideoFetchError: 找不到該 handle 對應的頻道。
        """
        clean_handle = handle.lstrip("@")
        logger.info("解析 handle: @%s", clean_handle)

        try:
            response = self._youtube.channels().list(
                part="id",
                forHandle=clean_handle,
            ).execute()
        except Exception as exc:
            raise VideoFetchError(f"解析 handle @{clean_handle} 失敗: {exc}") from exc

        items = response.get("items", [])
        if not items:
            raise VideoFetchError(f"找不到 handle @{clean_handle} 對應的頻道")

        channel_id = items[0]["id"]
        logger.info("handle @%s -> channel_id: %s", clean_handle, channel_id)
        return channel_id

    def ensure_channel_id(self, channel: ChannelConfig) -> str:
        """確保取得 channel_id，若只有 handle 則自動解析。"""
        if channel.channel_id:
            return channel.channel_id
        if channel.handle:
            return self.resolve_channel_id(channel.handle)
        raise VideoFetchError(f"頻道 {channel.name} 沒有 channel_id 也沒有 handle")

    @retry(max_retries=3, delay=2.0, backoff_factor=2.0, exceptions=(Exception,))
    def get_new_videos(
        self, channel: ChannelConfig, since_date: str
    ) -> list[VideoMetadata]:
        """取得頻道在指定日期之後的新影片。

        Args:
            channel: 頻道設定。
            since_date: 起始日期（YYYY-MM-DD 格式）。

        Returns:
            新影片的 metadata 列表。
        """
        channel_id = self.ensure_channel_id(channel)
        published_after = f"{since_date}T00:00:00Z"

        logger.info(
            "檢查頻道 %s (%s) 自 %s 以來的新影片",
            channel.name,
            channel_id,
            since_date,
        )

        try:
            response = self._youtube.search().list(
                part="snippet",
                channelId=channel_id,
                publishedAfter=published_after,
                type="video",
                order="date",
                maxResults=50,
            ).execute()
        except Exception as exc:
            raise VideoFetchError(
                f"搜尋頻道 {channel.name} 新影片失敗: {exc}"
            ) from exc

        items = response.get("items", [])
        logger.info("頻道 %s 找到 %d 支新影片", channel.name, len(items))

        videos: list[VideoMetadata] = []
        for item in items:
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]
            videos.append(
                VideoMetadata(
                    video_id=video_id,
                    title=snippet["title"],
                    channel_id=channel_id,
                    channel_name=snippet.get("channelTitle", channel.name),
                    published_at=datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    ),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    description=snippet.get("description", ""),
                    language=channel.language,
                )
            )

        return videos
