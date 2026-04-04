"""CLI 進入點與管線調度。"""

import argparse
import json
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from yt_finance_analyzer.config import Settings, get_settings, load_channels
from yt_finance_analyzer.database import Database
from yt_finance_analyzer.models import (
    DailyTrendAnalysis,
    VideoAnalysis,
    VideoMetadata,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    """設定 root logger。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calculate_week_range(date_str: str) -> tuple[str, str]:
    """給定任意日期，算出該週的 (week_start, week_end)（週一~週日）。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _load_analysis_from_file(
    analysis_dir: Path, video_id: str
) -> VideoAnalysis | None:
    """從 data/analysis/{video_id}.json 載入快取的分析結果。"""
    path = analysis_dir / f"{video_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VideoAnalysis.model_validate(data)
    except Exception as exc:
        logger.warning("載入分析結果失敗 %s: %s", video_id, exc)
        return None


def _load_daily_trend_from_file(
    analysis_dir: Path, date: str
) -> DailyTrendAnalysis | None:
    """從 data/analysis/trends/daily_{date}.json 載入每日趨勢。"""
    path = analysis_dir / "trends" / f"daily_{date}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DailyTrendAnalysis.model_validate(data)
    except Exception as exc:
        logger.warning("載入每日趨勢失敗 %s: %s", date, exc)
        return None


def _init_services(settings: Settings) -> dict:
    """初始化所有服務物件。"""
    from yt_finance_analyzer.analysis.claude_provider import ClaudeLLMProvider
    from yt_finance_analyzer.analysis.trend_analyzer import TrendAnalyzerService
    from yt_finance_analyzer.analysis.video_analyzer import VideoAnalyzerService
    from yt_finance_analyzer.delivery.email_sender import EmailSender
    from yt_finance_analyzer.ingestion.channel_checker import ChannelChecker
    from yt_finance_analyzer.ingestion.metadata_fetcher import MetadataFetcher
    from yt_finance_analyzer.ingestion.subtitle_fetcher import SubtitleFetcher
    from yt_finance_analyzer.reporting.report_generator import ReportGenerator
    from yt_finance_analyzer.reporting.weekly_report_generator import WeeklyReportGenerator
    from yt_finance_analyzer.transcription.whisper_provider import WhisperSTTProvider

    db = Database(settings.db_path)
    db.init_db()

    stt_provider = WhisperSTTProvider(settings.openai_api_key)
    llm_provider = ClaudeLLMProvider(settings.anthropic_api_key)

    return {
        "db": db,
        "channel_checker": ChannelChecker(settings),
        "metadata_fetcher": MetadataFetcher(settings),
        "subtitle_fetcher": SubtitleFetcher(settings, stt_provider),
        "video_analyzer": VideoAnalyzerService(settings, llm_provider),
        "trend_analyzer": TrendAnalyzerService(settings, llm_provider),
        "report_generator": ReportGenerator(settings),
        "weekly_report_generator": WeeklyReportGenerator(settings),
        "email_sender": EmailSender(settings),
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_fetch(
    settings: Settings, services: dict, date: str | None = None
) -> list[VideoMetadata]:
    """抓取所有 enabled 頻道的新影片。"""
    channels = load_channels()
    if not channels:
        logger.warning("未找到任何已啟用的頻道設定")
        return []

    db: Database = services["db"]
    checker = services["channel_checker"]
    since_date = date or datetime.now().strftime("%Y-%m-%d")

    all_new: list[VideoMetadata] = []
    for channel in channels:
        try:
            videos = checker.get_new_videos(channel, since_date)
            for video in videos:
                if not db.is_video_processed(video.video_id):
                    db.save_video_metadata(video)
                    all_new.append(video)
                    logger.info("新影片: %s (%s)", video.video_id, video.title)
                else:
                    logger.debug("已處理，跳過: %s", video.video_id)
        except Exception as exc:
            logger.error("頻道 %s 抓取失敗: %s", channel.name, exc)

    logger.info("共發現 %d 支新影片", len(all_new))
    return all_new


def cmd_analyze(
    settings: Settings,
    services: dict,
    date: str,
    new_videos: list[VideoMetadata] | None = None,
) -> list[VideoAnalysis]:
    """對指定日期的影片進行 LLM 分析。

    Args:
        settings: 設定。
        services: 服務物件字典。
        date: 目標日期 (YYYY-MM-DD)。
        new_videos: 若有已取得的 metadata 列表，直接使用；否則從 DB 查詢。

    Returns:
        成功分析的 VideoAnalysis 列表。
    """
    db: Database = services["db"]
    subtitle_fetcher = services["subtitle_fetcher"]
    video_analyzer = services["video_analyzer"]

    # 取得要處理的影片
    if new_videos is not None:
        videos_to_process = new_videos
    else:
        rows = db.get_videos_for_date(date)
        videos_to_process = [
            VideoMetadata(
                video_id=r["video_id"],
                title=r["title"],
                channel_id=r["channel_id"],
                channel_name=r["channel_name"],
                published_at=datetime.fromisoformat(r["published_at"]),
                url=r["url"],
                description=r["description"] or "",
                duration_seconds=r["duration_seconds"],
                language=r["language"],
            )
            for r in rows
            if r["status"] in ("pending", "transcript_done")
        ]

    if not videos_to_process:
        logger.info("無待分析影片 (%s)", date)
        return []

    # 限制每日最大處理數
    if len(videos_to_process) > settings.max_videos_per_day:
        logger.info(
            "影片數 %d 超過上限 %d，僅處理前 %d 支",
            len(videos_to_process),
            settings.max_videos_per_day,
            settings.max_videos_per_day,
        )
        videos_to_process = videos_to_process[: settings.max_videos_per_day]

    successful: list[VideoAnalysis] = []
    failed_count = 0

    for metadata in videos_to_process:
        vid = metadata.video_id
        start_time = time.time()
        try:
            logger.info("=== 開始處理影片: %s (%s) ===", vid, metadata.title)

            # 1. 取得逐字稿
            language = metadata.language or "zh-TW"
            transcript = subtitle_fetcher.get_transcript(vid, language)
            db.update_video_status(vid, "transcript_done")

            # 2. LLM 分析
            analysis = video_analyzer.analyze_video(metadata, transcript)
            db.update_video_status(vid, "analysis_done")

            successful.append(analysis)
            elapsed = time.time() - start_time
            logger.info("影片處理完成: %s (耗時 %.1f 秒)", vid, elapsed)

        except Exception as exc:
            failed_count += 1
            elapsed = time.time() - start_time
            logger.error("影片處理失敗: %s (耗時 %.1f 秒): %s", vid, elapsed, exc)
            try:
                db.update_video_status(vid, "failed", error_message=str(exc))
            except Exception:
                logger.exception("更新失敗狀態也失敗: %s", vid)

    logger.info(
        "分析完成: 成功 %d / 失敗 %d / 共 %d",
        len(successful),
        failed_count,
        len(videos_to_process),
    )
    return successful


def cmd_report(
    settings: Settings,
    services: dict,
    date: str,
    analyses: list[VideoAnalysis] | None = None,
) -> None:
    """產生個別報告與每日彙整報告。"""
    db: Database = services["db"]
    report_gen = services["report_generator"]
    trend_analyzer = services["trend_analyzer"]

    # 若未傳入 analyses，從檔案載入
    if analyses is None:
        rows = db.get_videos_for_date(date)
        analyses = []
        for r in rows:
            if r["status"] in ("analysis_done", "reported"):
                a = _load_analysis_from_file(settings.analysis_dir, r["video_id"])
                if a:
                    analyses.append(a)

    if not analyses:
        logger.warning("無可用分析結果，跳過報告產生 (%s)", date)
        return

    # 個別報告
    for analysis in analyses:
        try:
            path = report_gen.generate_individual_report(analysis)
            logger.info("個別報告: %s", path)
        except Exception as exc:
            logger.error("產生個別報告失敗 %s: %s", analysis.video_id, exc)

    # 每日趨勢 + 彙整報告
    try:
        trend = trend_analyzer.analyze_daily_trend(analyses, date)
        digest_path = report_gen.generate_daily_digest(trend, analyses, date)
        logger.info("每日彙整報告: %s", digest_path)
    except Exception as exc:
        logger.error("產生每日彙整報告失敗: %s", exc)

    # 更新狀態為 reported
    for analysis in analyses:
        try:
            db.update_video_status(analysis.video_id, "reported")
        except Exception:
            pass


def cmd_weekly_report(settings: Settings, services: dict, week_of: str) -> None:
    """產生每週彙整報告。"""
    db: Database = services["db"]
    trend_analyzer = services["trend_analyzer"]
    weekly_report_gen = services["weekly_report_generator"]

    week_start, week_end = _calculate_week_range(week_of)
    logger.info("週報範圍: %s ~ %s", week_start, week_end)

    # 從 DB 取得該週影片
    rows = db.get_videos_for_week(week_start, week_end)
    if not rows:
        logger.warning("該週無影片資料: %s ~ %s", week_start, week_end)
        return

    # 載入分析結果
    analyses: list[VideoAnalysis] = []
    for r in rows:
        if r["status"] in ("analysis_done", "reported"):
            a = _load_analysis_from_file(settings.analysis_dir, r["video_id"])
            if a:
                analyses.append(a)

    if not analyses:
        logger.warning("該週無可用分析結果: %s ~ %s", week_start, week_end)
        return

    logger.info("載入 %d 支影片分析結果", len(analyses))

    # 載入每日趨勢
    daily_trends: list[DailyTrendAnalysis] = []
    current = datetime.strptime(week_start, "%Y-%m-%d")
    end = datetime.strptime(week_end, "%Y-%m-%d")
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        trend = _load_daily_trend_from_file(settings.analysis_dir, date_str)
        if trend:
            daily_trends.append(trend)
        current += timedelta(days=1)

    # 週趨勢分析
    weekly_trend = trend_analyzer.analyze_weekly_trend(analyses, week_start, week_end)

    # 產生週報
    date_range = f"{week_start}_{week_end}"
    path = weekly_report_gen.generate_weekly_digest(weekly_trend, daily_trends, date_range)
    logger.info("每週彙整報告: %s", path)


def cmd_send(settings: Settings, services: dict, date: str) -> None:
    """寄送每日報告 email。"""
    email_sender = services["email_sender"]

    # 找到每日彙整報告
    digest_path = settings.reports_dir / date / "daily_digest.html"
    if not digest_path.exists():
        logger.warning("每日彙整報告不存在，無法寄送: %s", digest_path)
        return

    # 載入每日趨勢以取得 sentiment 和影片數
    trend = _load_daily_trend_from_file(settings.analysis_dir, date)
    overall_sentiment = trend.overall_sentiment if trend else ""
    video_count = trend.total_videos_analyzed if trend else 0

    email_sender.send_daily_digest(
        html_path=digest_path,
        date=date,
        overall_sentiment=overall_sentiment,
        video_count=video_count,
        attach_individual=True,
    )


def cmd_send_weekly(settings: Settings, services: dict, week_of: str) -> None:
    """寄送週報 email。"""
    email_sender = services["email_sender"]

    week_start, week_end = _calculate_week_range(week_of)
    date_range = f"{week_start}_{week_end}"

    weekly_path = settings.reports_dir / "weekly" / f"weekly_{date_range}.html"
    if not weekly_path.exists():
        logger.warning("每週彙整報告不存在，無法寄送: %s", weekly_path)
        return

    email_sender.send_weekly_digest(html_path=weekly_path, week_range=date_range)


def cmd_status(settings: Settings, services: dict, date: str) -> None:
    """查看指定日期的影片處理狀態。"""
    db: Database = services["db"]
    rows = db.get_videos_for_date(date)

    if not rows:
        print(f"無 {date} 的影片紀錄")
        return

    # 統計
    status_counts: dict[str, int] = {}
    for r in rows:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\n{'='*60}")
    print(f"  日期: {date}  |  共 {len(rows)} 支影片")
    print(f"{'='*60}")

    for status, count in sorted(status_counts.items()):
        print(f"  {status:20s} : {count}")

    print(f"{'='*60}")
    print()

    for r in rows:
        err = f" [{r['error_message']}]" if r.get("error_message") else ""
        print(f"  [{r['status']:15s}] {r['video_id']} — {r['title']}{err}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_daily_pipeline(settings: Settings, services: dict, date: str) -> None:
    """完整每日管線。"""
    pipeline_start = time.time()
    logger.info("========== 每日管線開始: %s ==========", date)

    # 1. 抓取新影片
    new_videos = cmd_fetch(settings, services, date=date)

    # 2. 分析
    analyses = cmd_analyze(settings, services, date, new_videos=new_videos)

    # 3. 報告
    if analyses:
        cmd_report(settings, services, date, analyses=analyses)
    else:
        logger.info("無成功分析結果，跳過報告產生")

    # 4. 寄送 email
    cmd_send(settings, services, date)

    # 5. 清理音訊暫存
    if settings.audio_dir.exists():
        try:
            shutil.rmtree(settings.audio_dir)
            logger.info("已清理音訊暫存目錄: %s", settings.audio_dir)
        except Exception as exc:
            logger.warning("清理音訊暫存失敗: %s", exc)

    elapsed = time.time() - pipeline_start
    logger.info(
        "========== 每日管線完成: %s (耗時 %.1f 秒) ==========",
        date,
        elapsed,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """建立 CLI 參數解析。"""
    # 共用 parent parser，讓所有子命令都繼承 --verbose
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--verbose", "-v", action="store_true", help="開啟 DEBUG 日誌"
    )

    parser = argparse.ArgumentParser(
        prog="yt-finance-analyzer",
        description="YouTube 財經影片自動分析系統",
        parents=[parent],
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run
    p_run = subparsers.add_parser("run", parents=[parent], help="執行完整每日管線")
    p_run.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="目標日期 (YYYY-MM-DD)，預設今天",
    )

    # fetch
    subparsers.add_parser("fetch", parents=[parent], help="只抓取新影片")

    # analyze
    p_analyze = subparsers.add_parser("analyze", parents=[parent], help="只對已抓取影片做分析")
    p_analyze.add_argument("--date", required=True, help="目標日期 (YYYY-MM-DD)")

    # report
    p_report = subparsers.add_parser("report", parents=[parent], help="只產生報告")
    p_report.add_argument("--date", required=True, help="目標日期 (YYYY-MM-DD)")

    # weekly-report
    p_weekly = subparsers.add_parser("weekly-report", parents=[parent], help="產生每週彙整報告")
    p_weekly.add_argument(
        "--week-of",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="指定日期所在的週 (YYYY-MM-DD)，預設今天",
    )

    # send
    p_send = subparsers.add_parser("send", parents=[parent], help="寄送每日報告 email")
    p_send.add_argument("--date", required=True, help="目標日期 (YYYY-MM-DD)")

    # send-weekly
    p_send_weekly = subparsers.add_parser("send-weekly", parents=[parent], help="寄送週報 email")
    p_send_weekly.add_argument("--week-of", required=True, help="指定日期所在的週")

    # status
    p_status = subparsers.add_parser("status", parents=[parent], help="查看處理狀態")
    p_status.add_argument("--date", required=True, help="目標日期 (YYYY-MM-DD)")

    return parser.parse_args()


def main() -> None:
    """CLI 進入點。"""
    args = _parse_args()
    setup_logging(verbose=args.verbose)

    if not args.command:
        logger.error("請指定子命令。執行 yt-finance-analyzer --help 查看用法。")
        return

    settings = get_settings()
    services = _init_services(settings)

    try:
        if args.command == "run":
            run_daily_pipeline(settings, services, args.date)

        elif args.command == "fetch":
            cmd_fetch(settings, services)

        elif args.command == "analyze":
            cmd_analyze(settings, services, args.date)

        elif args.command == "report":
            cmd_report(settings, services, args.date)

        elif args.command == "weekly-report":
            cmd_weekly_report(settings, services, args.week_of)

        elif args.command == "send":
            cmd_send(settings, services, args.date)

        elif args.command == "send-weekly":
            cmd_send_weekly(settings, services, args.week_of)

        elif args.command == "status":
            cmd_status(settings, services, args.date)

    finally:
        services["db"].close()


if __name__ == "__main__":
    main()
