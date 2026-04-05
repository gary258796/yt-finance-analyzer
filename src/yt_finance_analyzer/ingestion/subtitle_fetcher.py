"""透過 yt-dlp 抓取影片字幕或下載音訊，整合字幕/STT 流程產出逐字稿。"""

import logging
import re
import urllib.request
from pathlib import Path

import yt_dlp

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
        self._cookies_file = settings.youtube_cookies_file or None

    @retry(max_retries=2, delay=3.0, backoff_factor=2.0, exceptions=(Exception,))
    def fetch_subtitle(self, video_id: str, language: str = "zh-TW") -> str | None:
        """嘗試用 yt-dlp 抓取影片字幕。

        透過 extract_info 取得字幕 URL，再直接下載 VTT 內容。
        優先手動字幕，其次自動字幕。

        Args:
            video_id: YouTube 影片 ID。
            language: 目標語言代碼。

        Returns:
            字幕文字內容，若無字幕則回傳 None。
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info("嘗試抓取字幕: %s (語言: %s)", video_id, language)

        lang_base = language.split("-")[0]

        ydl_opts: dict = {"skip_download": True, "quiet": True, "no_warnings": True}
        if self._cookies_file:
            ydl_opts["cookiefile"] = self._cookies_file
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            logger.warning("取得影片資訊失敗 %s: %s", video_id, exc)
            return None

        if not info:
            return None

        # 嘗試順序：手動字幕 -> 自動字幕
        for sub_key, sub_type in (("subtitles", "手動"), ("automatic_captions", "自動")):
            subs = info.get(sub_key, {})
            for lang in (language, lang_base):
                if lang not in subs:
                    continue
                # 在可用格式中找 vtt
                vtt_url = None
                for entry in subs[lang]:
                    if entry.get("ext") == "vtt":
                        vtt_url = entry.get("url")
                        break
                if not vtt_url:
                    continue

                logger.info("下載%s字幕: %s (語言: %s)", sub_type, video_id, lang)
                vtt_content = self._download_vtt(vtt_url)
                if vtt_content:
                    text = self._parse_vtt_content(vtt_content)
                    if text:
                        # 儲存原始 VTT 檔案供除錯
                        self._save_vtt(video_id, lang, vtt_content)
                        logger.info(
                            "取得%s字幕: %s (語言: %s, %d 字元)",
                            sub_type, video_id, lang, len(text),
                        )
                        return text

        logger.info("影片 %s 無可用字幕", video_id)
        return None

    def _download_vtt(self, vtt_url: str) -> str | None:
        """從 URL 下載 VTT 字幕內容。"""
        try:
            req = urllib.request.Request(vtt_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            logger.warning("下載 VTT 字幕失敗: %s", exc)
            return None

    def _save_vtt(self, video_id: str, lang: str, content: str) -> None:
        """儲存原始 VTT 檔案供除錯。"""
        output_dir = self._settings.transcripts_dir / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        vtt_path = output_dir / f"{video_id}.{lang}.vtt"
        vtt_path.write_text(content, encoding="utf-8")

    def _parse_vtt_content(self, vtt_content: str) -> str | None:
        """解析 VTT 字幕內容為純文字。"""
        lines: list[str] = []
        for line in vtt_content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("WEBVTT"):
                continue
            if line.startswith("Kind:") or line.startswith("Language:"):
                continue
            if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", line):
                continue
            if re.match(r"^\d+$", line):
                continue
            # 移除 VTT 標記 (e.g., <c>, </c>, <00:00:01.000>)
            line = re.sub(r"<[^>]+>", "", line)
            if line:
                lines.append(line)

        # 去重（VTT 自動字幕常有重複行）
        seen: set[str] = set()
        unique: list[str] = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)

        return "\n".join(unique) if unique else None

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

        ydl_opts: dict = {
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
        if self._cookies_file:
            ydl_opts["cookiefile"] = self._cookies_file

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
