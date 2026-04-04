"""Email 寄送模組，透過 SMTP 發送 HTML 報告。"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from yt_finance_analyzer.config import Settings
from yt_finance_analyzer.models import EmailSendError
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)


class EmailSender:
    """透過 SMTP 寄送 HTML 報告 email。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @retry(max_retries=2, delay=5.0, backoff_factor=2.0, exceptions=(smtplib.SMTPException, OSError))
    def _send_email(self, subject: str, html_body: str, attachments: list[Path] | None = None) -> None:
        """底層寄送方法，透過 SMTP 發送 email。

        Args:
            subject: 郵件主旨。
            html_body: HTML 郵件內容。
            attachments: 要附加的 HTML 檔案路徑列表。

        Raises:
            smtplib.SMTPException: SMTP 連線或寄送失敗。
        """
        recipients = self._settings.email_recipients
        if not recipients:
            logger.warning("未設定收件人 (EMAIL_TO)，跳過寄送")
            return

        msg = MIMEMultipart("mixed")
        msg["From"] = self._settings.email_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        # HTML 內容作為 email body
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # 附件
        if attachments:
            for file_path in attachments:
                if not file_path.exists():
                    logger.warning("附件不存在，跳過: %s", file_path)
                    continue
                attachment_html = file_path.read_text(encoding="utf-8")
                part = MIMEText(attachment_html, "html", "utf-8")
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=file_path.name,
                )
                msg.attach(part)

        logger.info(
            "開始寄送 email: 主旨='%s', 收件人=%s",
            subject,
            recipients,
        )

        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
            server.starttls()
            server.login(self._settings.smtp_username, self._settings.smtp_password)
            server.sendmail(self._settings.email_from, recipients, msg.as_string())

        logger.info("Email 寄送成功: %s", subject)

    def send_daily_digest(
        self,
        html_path: Path,
        date: str,
        overall_sentiment: str = "",
        video_count: int = 0,
        attach_individual: bool = False,
    ) -> None:
        """寄送每日彙整報告。

        Args:
            html_path: 每日彙整 HTML 報告路徑。
            date: 日期字串 (YYYY-MM-DD)。
            overall_sentiment: 整體情緒 (bullish/bearish/neutral/mixed)。
            video_count: 影片數量。
            attach_individual: 是否附加個別影片報告。
        """
        sentiment_label = _sentiment_display(overall_sentiment)
        subject = f"[財經日報] {date} — {sentiment_label} — 共 {video_count} 支影片分析"

        try:
            html_body = html_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("讀取每日彙整報告失敗 %s: %s", html_path, exc)
            return

        # 蒐集個別報告作為附件
        attachments: list[Path] = []
        if attach_individual:
            report_dir = html_path.parent
            for f in sorted(report_dir.glob("*.html")):
                if f.name != "daily_digest.html":
                    attachments.append(f)
            if attachments:
                logger.info("附加 %d 個個別報告", len(attachments))

        try:
            self._send_email(subject, html_body, attachments or None)
        except Exception as exc:
            logger.error("寄送每日報告失敗: %s", exc)

    def send_weekly_digest(self, html_path: Path, week_range: str) -> None:
        """寄送每週彙整報告。

        Args:
            html_path: 每週彙整 HTML 報告路徑。
            week_range: 週期間字串（如 "2025-01-06_2025-01-12"）。
        """
        display_range = week_range.replace("_", " ~ ")
        subject = f"[財經週報] {display_range} — 本週趨勢分析"

        try:
            html_body = html_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("讀取每週彙整報告失敗 %s: %s", html_path, exc)
            return

        try:
            self._send_email(subject, html_body)
        except Exception as exc:
            logger.error("寄送週報失敗: %s", exc)


def _sentiment_display(sentiment: str) -> str:
    """將 sentiment 值轉為中文顯示。"""
    mapping = {
        "bullish": "偏多",
        "bearish": "偏空",
        "neutral": "中性",
        "mixed": "混合",
    }
    return mapping.get(sentiment, sentiment or "—")
