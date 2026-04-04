"""端對端測試：驗證影片抓取 + 字幕轉錄流程。

使用 channels.yaml 中的真實頻道，依序測試：
1. ChannelChecker — 取得頻道最近影片
2. MetadataFetcher — 取得完整 metadata
3. SubtitleFetcher — 抓取字幕並產生 TranscriptResult
"""

import logging
import sys
from datetime import datetime, timedelta

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("e2e_test")


def main() -> None:
    from yt_finance_analyzer.config import get_settings, load_channels
    from yt_finance_analyzer.ingestion.channel_checker import ChannelChecker
    from yt_finance_analyzer.ingestion.metadata_fetcher import MetadataFetcher
    from yt_finance_analyzer.ingestion.subtitle_fetcher import SubtitleFetcher

    # ── Step 0: 載入設定 ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("Step 0: 載入設定")
    settings = get_settings()
    channels = load_channels()

    if not channels:
        logger.error("channels.yaml 中沒有啟用的頻道")
        sys.exit(1)

    channel = channels[0]
    logger.info("測試頻道: %s (channel_id=%s, handle=%s)", channel.name, channel.channel_id, channel.handle)
    logger.info("YouTube API Key: %s...", settings.youtube_api_key[:8] if settings.youtube_api_key else "未設定")

    if not settings.youtube_api_key:
        logger.error("請在 .env 中設定 YOUTUBE_API_KEY")
        sys.exit(1)

    # ── Step 1: ChannelChecker — 取得最近影片 ────────────
    logger.info("=" * 60)
    logger.info("Step 1: ChannelChecker.get_new_videos()")

    checker = ChannelChecker(settings)
    since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    logger.info("搜尋 %s 以來的影片", since_date)

    videos = checker.get_new_videos(channel, since_date)
    logger.info("找到 %d 支影片", len(videos))

    if not videos:
        logger.warning("最近 7 天沒有新影片，嘗試擴大到 30 天")
        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        videos = checker.get_new_videos(channel, since_date)
        logger.info("找到 %d 支影片", len(videos))

    if not videos:
        logger.error("找不到任何影片，測試中止")
        sys.exit(1)

    for i, v in enumerate(videos[:5]):
        logger.info("  [%d] %s — %s (%s)", i + 1, v.video_id, v.title, v.published_at.strftime("%Y-%m-%d"))

    # ── Step 2: MetadataFetcher — 取得完整 metadata ─────
    logger.info("=" * 60)
    logger.info("Step 2: MetadataFetcher.fetch_metadata()")

    fetcher = MetadataFetcher(settings)
    target_video = videos[0]
    metadata = fetcher.fetch_metadata(target_video.video_id, channel.language)

    logger.info("影片 ID: %s", metadata.video_id)
    logger.info("標題: %s", metadata.title)
    logger.info("頻道: %s", metadata.channel_name)
    logger.info("發布時間: %s", metadata.published_at)
    logger.info("時長: %s 秒", metadata.duration_seconds)
    logger.info("語言: %s", metadata.language)
    logger.info("網址: %s", metadata.url)
    logger.info("說明: %s...", metadata.description[:100] if metadata.description else "(無)")

    # ── Step 3: SubtitleFetcher — 抓取字幕 ──────────────
    logger.info("=" * 60)
    logger.info("Step 3: SubtitleFetcher.get_transcript()")
    logger.info("注意：此步驟只測試字幕抓取，不會使用 Whisper STT")

    sub_fetcher = SubtitleFetcher(settings, stt_provider=None)

    # 先單獨測試 fetch_subtitle
    subtitle_text = sub_fetcher.fetch_subtitle(metadata.video_id, channel.language or "zh-TW")

    if subtitle_text:
        logger.info("字幕抓取成功！長度: %d 字元", len(subtitle_text))
        logger.info("字幕前 200 字: %s", subtitle_text[:200])

        # 完整流程: get_transcript
        transcript = sub_fetcher.get_transcript(metadata.video_id, channel.language or "zh-TW")
        logger.info("─" * 40)
        logger.info("TranscriptResult:")
        logger.info("  video_id: %s", transcript.video_id)
        logger.info("  source: %s", transcript.source)
        logger.info("  language: %s", transcript.language)
        logger.info("  char_count: %d", transcript.char_count)
        logger.info("  word_count: %d", transcript.word_count)
        logger.info("  cleaned_text 前 300 字: %s", transcript.cleaned_text[:300])
    else:
        logger.warning("此影片無可用字幕（需要 Whisper STT 才能轉錄）")

    # ── 結果彙整 ─────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("端對端測試完成！")
    logger.info("  ChannelChecker: OK (%d 支影片)", len(videos))
    logger.info("  MetadataFetcher: OK (%s)", metadata.title)
    logger.info("  SubtitleFetcher: %s", "OK (有字幕)" if subtitle_text else "OK (無字幕，需 STT)")


if __name__ == "__main__":
    main()
