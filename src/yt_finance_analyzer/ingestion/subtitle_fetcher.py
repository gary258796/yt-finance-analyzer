"""透過 youtube-transcript-api 抓取字幕，或用 yt-dlp 下載音訊進行 STT。"""

import logging
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import TranscriptResult, VideoFetchError
from yt_finance_analyzer.transcription.base import STTProvider
from yt_finance_analyzer.transcription.processor import process_transcript
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)


class SubtitleFetcher:
    """抓取 YouTube 影片字幕或下載音訊以進行 STT。"""

    def __init__(self, settings: Settings, stt_provider: STTProvider | None = None) -> None:
        self._settings = settings
        self._stt_provider = stt_provider
        self._ytt = YouTubeTranscriptApi()

    @retry(max_retries=2, delay=3.0, backoff_factor=2.0, exceptions=(Exception,))
    def fetch_subtitle(self, video_id: str, language: str = "zh-TW") -> str | None:
        """透過 youtube-transcript-api 抓取影片字幕。

        優先手動字幕，其次自動產生字幕。

        Args:
            video_id: YouTube 影片 ID。
            language: 目標語言代碼。

        Returns:
            字幕文字內容，若無字幕則回傳 None。
        """
        logger.info("嘗試抓取字幕: %s (語言: %s)", video_id, language)
        lang_base = language.split("-")[0]
        lang_candidates = [language, lang_base]

        try:
            transcript_list = self._ytt.list(video_id)
        except Exception as exc:
            logger.warning("列出字幕失敗 %s: %s", video_id, exc)
            return None

        # 優先手動字幕，其次自動字幕
        transcript = None
        source_type = ""
        try:
            transcript = transcript_list.find_transcript(lang_candidates)
            source_type = "手動"
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(lang_candidates)
                source_type = "自動"
            except Exception:
                logger.info("影片 %s 無可用字幕 (語言: %s)", video_id, language)
                return None

        # 取得字幕內容
        snippets = transcript.fetch()
        text = "\n".join(entry.text for entry in snippets)

        if not text.strip():
            logger.info("影片 %s 字幕內容為空", video_id)
            return None

        # 儲存供除錯
        self._save_transcript(video_id, language, text)
        logger.info(
            "取得%s字幕: %s (語言: %s, %d 字元)",
            source_type, video_id, language, len(text),
        )
        return text

    def _save_transcript(self, video_id: str, lang: str, content: str) -> None:
        """儲存字幕文字檔供除錯。"""
        output_dir = self._settings.transcripts_dir / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        txt_path = output_dir / f"{video_id}.{lang}.txt"
        txt_path.write_text(content, encoding="utf-8")

    @retry(max_retries=2, delay=3.0, backoff_factor=2.0, exceptions=(Exception,))
    def download_audio(self, video_id: str) -> Path:
        """下載影片音訊檔案（mp3 格式，限制品質以節省空間）。

        Args:
            video_id: YouTube 影片 ID。

        Returns:
            音訊檔案路徑。

        Raises:
            VideoFetchError: 下載音訊失敗。
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        output_dir = self._settings.audio_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{video_id}.mp3"

        if output_path.exists():
            logger.info("音訊檔案已存在: %s", output_path)
            return output_path

        logger.info("下載音訊: %s", video_id)

        ydl_opts = {
            "format": "bestaudio[abr<=128]",
            "outtmpl": str(output_dir / f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as exc:
            raise VideoFetchError(f"下載音訊失敗 {video_id}: {exc}") from exc

        if not output_path.exists():
            raise VideoFetchError(f"音訊檔案未產生: {output_path}")

        logger.info("音訊下載完成: %s (%.1f MB)", output_path, output_path.stat().st_size / 1024 / 1024)
        return output_path

    def get_transcript(self, video_id: str, language: str = "zh-TW") -> TranscriptResult:
        """整合字幕或 STT 流程，取得影片逐字稿。

        優先使用字幕，若無字幕則下載音訊並透過 STT 轉錄。

        Args:
            video_id: YouTube 影片 ID。
            language: 目標語言。

        Returns:
            TranscriptResult 逐字稿結果。

        Raises:
            VideoFetchError: 無法取得逐字稿。
        """
        subtitle_text = self.fetch_subtitle(video_id, language)
        if subtitle_text:
            logger.info("使用字幕作為逐字稿: %s", video_id)
            return process_transcript(video_id, subtitle_text, "subtitle", language)

        if self._stt_provider is None:
            raise VideoFetchError(
                f"影片 {video_id} 無字幕且未設定 STT provider"
            )

        logger.info("無字幕，使用 STT 轉錄: %s", video_id)
        audio_path = self.download_audio(video_id)
        raw_text = self._stt_provider.transcribe(audio_path, language)
        return process_transcript(video_id, raw_text, "whisper", language)
