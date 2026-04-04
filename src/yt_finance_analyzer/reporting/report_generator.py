"""個別影片報告與每日彙整報告產生器。"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import DailyTrendAnalysis, ReportGenerationError, VideoAnalysis

logger = logging.getLogger(__name__)

# 模板目錄位於本檔案所在目錄下的 templates/
_TEMPLATE_DIR = Path(__file__).parent / "templates"


class ReportGenerator:
    """產生個別影片 HTML 報告與每日彙整報告。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def generate_individual_report(self, analysis: VideoAnalysis) -> Path:
        """產生單支影片 HTML 報告。

        Args:
            analysis: 影片分析結果。

        Returns:
            報告檔案路徑。

        Raises:
            ReportGenerationError: 報告產生失敗。
        """
        try:
            date_str = analysis.published_at.strftime("%Y-%m-%d")
            output_dir = self._settings.reports_dir / date_str
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{analysis.video_id}.html"

            template = self._env.get_template("individual_report.html.j2")
            html = template.render(analysis=analysis)

            output_path.write_text(html, encoding="utf-8")
            logger.info("個別報告已產生: %s", output_path)
            return output_path

        except Exception as exc:
            raise ReportGenerationError(
                f"產生個別報告失敗 ({analysis.video_id}): {exc}"
            ) from exc

    def generate_daily_digest(
        self,
        trend: DailyTrendAnalysis,
        analyses: list[VideoAnalysis],
        date: str,
    ) -> Path:
        """產生每日彙整 HTML 報告。

        Args:
            trend: 每日趨勢分析結果。
            analyses: 當天所有影片的分析結果。
            date: 日期字串（YYYY-MM-DD）。

        Returns:
            報告檔案路徑。

        Raises:
            ReportGenerationError: 報告產生失敗。
        """
        try:
            output_dir = self._settings.reports_dir / date
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "daily_digest.html"

            template = self._env.get_template("daily_digest.html.j2")
            html = template.render(trend=trend, analyses=analyses)

            output_path.write_text(html, encoding="utf-8")
            logger.info("每日彙整報告已產生: %s", output_path)
            return output_path

        except Exception as exc:
            raise ReportGenerationError(
                f"產生每日彙整報告失敗 ({date}): {exc}"
            ) from exc
