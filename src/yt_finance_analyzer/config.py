"""應用程式設定模組，使用 pydantic-settings 從 .env 讀取設定，並載入 channels.yaml。"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseModel):
    """單一 YouTube 頻道設定。channel_id 和 handle 至少填一個。"""

    channel_id: str | None = None
    handle: str | None = None
    name: str
    language: str = "zh-TW"
    enabled: bool = True

    @model_validator(mode="after")
    def check_id_or_handle(self) -> "ChannelConfig":
        if not self.channel_id and not self.handle:
            raise ValueError("channel_id 和 handle 至少需填一個")
        return self


class Settings(BaseSettings):
    """應用程式主設定，從環境變數（.env 檔案）讀取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # YouTube Data API v3
    youtube_api_key: str = ""

    # Anthropic API (Claude LLM)
    anthropic_api_key: str = ""

    # OpenAI API (Whisper STT)
    openai_api_key: str = ""

    # Email SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # Processing limits
    max_videos_per_day: int = 20
    max_transcript_chars: int = 50000

    # Data directory
    data_dir: Path = Path("./data")

    @field_validator("data_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, v: Any) -> Path:
        return Path(v).resolve()

    @property
    def email_recipients(self) -> list[str]:
        """將逗號分隔的收件人字串轉為列表。"""
        if not self.email_to:
            return []
        return [addr.strip() for addr in self.email_to.split(",") if addr.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "yt_finance.db"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def analysis_dir(self) -> Path:
        return self.data_dir / "analysis"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


def load_channels(config_path: Path | None = None) -> list[ChannelConfig]:
    """從 channels.yaml 載入頻道設定，僅回傳 enabled=True 的頻道。"""
    if config_path is None:
        config_path = Path("config/channels.yaml")

    if not config_path.exists():
        return []

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "channels" not in data:
        return []

    channels = [ChannelConfig(**ch) for ch in data["channels"]]
    return [ch for ch in channels if ch.enabled]


def get_settings() -> Settings:
    """取得應用程式設定的單例。"""
    return Settings()
