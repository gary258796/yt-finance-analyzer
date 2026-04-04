"""每週彙整報告產生器。"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import (
    DailyTrendAnalysis,
    ReportGenerationError,
    WeeklyTrendAnalysis,
)

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


class WeeklyReportGenerator:
    """產生每週彙整 HTML 報告。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def generate_weekly_digest(
        self,
        trend: WeeklyTrendAnalysis,
        daily_trends: list[DailyTrendAnalysis],
        date_range: str,
    ) -> Path:
        """產生每週彙整 HTML 報告。

        Args:
            trend: 每週趨勢分析結果。
            daily_trends: 本週每日趨勢分析列表。
            date_range: 週期間字串（如 "2025-01-06_2025-01-12"）。

        Returns:
            報告檔案路徑。

        Raises:
            ReportGenerationError: 報告產生失敗。
        """
        try:
            output_dir = self._settings.reports_dir / "weekly"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"weekly_{date_range}.html"

            template = self._env.get_template("weekly_digest.html.j2")
            html = template.render(trend=trend, daily_trends=daily_trends)

            output_path.write_text(html, encoding="utf-8")
            logger.info("每週彙整報告已產生: %s", output_path)
            return output_path

        except Exception as exc:
            raise ReportGenerationError(
                f"產生每週彙整報告失敗 ({date_range}): {exc}"
            ) from exc
