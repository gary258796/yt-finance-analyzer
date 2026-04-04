# Claude Code Prompt — YouTube 財經影片自動分析系統

## 你的角色

你是一位資深全端工程師，負責設計並實作一套完整的「YouTube 財經影片自動分析系統」。請使用 Python 實作，遵循下方所有規範，從零開始建構此專案。

---

## 專案總覽

此系統每天自動抓取指定 YouTube 頻道的新影片，將影片內容轉成文字，透過 LLM 進行結構化財經分析，產出 HTML 報告並透過 Email 寄送。

---

## 技術選型（請嚴格遵循）

- **語言**：Python 3.11+
- **套件管理**：使用 `pyproject.toml`（PEP 621），不要用 `setup.py` 或 `requirements.txt`
- **YouTube 資料抓取**：`yt-dlp`（抓 metadata、字幕、音訊）
- **YouTube API**：`google-api-python-client`（檢查頻道新影片）
- **語音轉文字**：設計 abstract interface，預設實作 OpenAI Whisper API
- **LLM 分析**：設計 abstract interface，預設實作 Anthropic Claude API（使用 `anthropic` SDK）
- **HTML 報告**：`Jinja2` 模板
- **Email 發送**：Python 內建 `smtplib` + `email.mime`
- **資料儲存**：SQLite（透過 `sqlite3`），用於追蹤影片處理狀態
- **設定管理**：`pydantic-settings`，從 `.env` 讀取設定
- **日誌**：Python 內建 `logging`，structured log format
- **排程**：提供 `cron` 指令範例，主程式本身是 CLI 可直接執行
- **非同步**：不需要 async，用同步架構即可

---

## 專案結構（請嚴格遵循此目錄結構）

```
yt-finance-analyzer/
├── pyproject.toml
├── .env.example                  # 環境變數範本
├── README.md
├── config/
│   └── channels.yaml             # YouTube 頻道設定檔
├── src/
│   └── yt_finance_analyzer/
│       ├── __init__.py
│       ├── main.py               # CLI 進入點，主流程調度
│       ├── config.py             # pydantic-settings 設定
│       ├── database.py           # SQLite 資料庫操作
│       ├── models.py             # 所有 Pydantic data models / schemas
│       │
│       ├── ingestion/            # 子模組：影片抓取
│       │   ├── __init__.py
│       │   ├── channel_checker.py    # 檢查頻道新影片
│       │   ├── metadata_fetcher.py   # 抓取影片 metadata
│       │   └── subtitle_fetcher.py   # 抓取字幕 / 下載音訊
│       │
│       ├── transcription/        # 子模組：語音轉文字
│       │   ├── __init__.py
│       │   ├── base.py           # STT abstract interface
│       │   ├── whisper_provider.py   # OpenAI Whisper 實作
│       │   └── processor.py      # 逐字稿前處理與清洗
│       │
│       ├── analysis/             # 子模組：LLM 分析
│       │   ├── __init__.py
│       │   ├── base.py           # LLM abstract interface
│       │   ├── claude_provider.py    # Anthropic Claude 實作
│       │   ├── prompts.py        # 所有 prompt templates
│       │   ├── schema_validator.py   # JSON schema 驗證
│       │   ├── video_analyzer.py     # 單支影片分析
│       │   └── trend_analyzer.py     # 每日趨勢彙整分析
│       │
│       ├── reporting/            # 子模組：報告產生
│       │   ├── __init__.py
│       │   ├── report_generator.py   # 報告產生邏輯
│       │   ├── weekly_report_generator.py  # 週報產生邏輯
│       │   └── templates/
│       │       ├── individual_report.html.j2
│       │       ├── daily_digest.html.j2
│       │       └── weekly_digest.html.j2
│       │
│       ├── delivery/             # 子模組：Email 寄送
│       │   ├── __init__.py
│       │   └── email_sender.py
│       │
│       └── utils/                # 共用工具
│           ├── __init__.py
│           ├── retry.py          # retry decorator
│           └── text_processing.py    # 文字清洗工具
│
├── data/                         # runtime 資料目錄（gitignore）
│   ├── db/                       # SQLite 資料庫
│   ├── transcripts/              # 逐字稿存放
│   ├── analysis/                 # 分析結果 JSON
│   ├── reports/                  # 產出的 HTML 報告
│   └── audio/                    # 暫存音訊檔
│
└── tests/                        # 測試（先建好結構，不需要寫完整測試）
    ├── __init__.py
    ├── test_models.py
    └── test_schema_validator.py
```

---

## 實作順序（請依此順序逐步完成）

### Phase 1：基礎建設

#### Step 1.1 — `pyproject.toml`
建立專案設定，列出所有 dependencies。包含一個 `[project.scripts]` entry point：
```
yt-finance-analyzer = "yt_finance_analyzer.main:main"
```

#### Step 1.2 — `.env.example`
列出所有需要的環境變數，附上說明註解：
```env
# YouTube Data API v3 Key
YOUTUBE_API_KEY=your_youtube_api_key

# Anthropic API Key (for Claude LLM analysis)
ANTHROPIC_API_KEY=your_anthropic_api_key

# OpenAI API Key (for Whisper STT, only needed if videos lack subtitles)
OPENAI_API_KEY=your_openai_api_key

# Email SMTP settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient1@example.com,recipient2@example.com

# Processing limits
MAX_VIDEOS_PER_DAY=20
MAX_TRANSCRIPT_CHARS=50000

# Data directory
DATA_DIR=./data
```

#### Step 1.3 — `config.py`
使用 `pydantic-settings` 的 `BaseSettings`，從 `.env` 讀取所有設定。同時讀取 `channels.yaml`。

#### Step 1.4 — `channels.yaml`
```yaml
channels:
  - channel_id: "UC_EXAMPLE_1"
    name: "頻道名稱1"
    language: "zh-TW"
    enabled: true
  - channel_id: "UC_EXAMPLE_2"
    name: "頻道名稱2"
    language: "en"
    enabled: true
```

#### Step 1.5 — `models.py`
定義以下 Pydantic models（全部用 `pydantic.BaseModel`）：

```python
class VideoMetadata(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_name: str
    published_at: datetime
    url: str
    description: str
    duration_seconds: int | None = None
    language: str | None = None

class TranscriptResult(BaseModel):
    video_id: str
    source: Literal["subtitle", "whisper"]  # 來源標記
    raw_text: str          # 原始逐字稿
    cleaned_text: str      # 清洗後版本
    language: str
    char_count: int
    word_count: int

class VideoAnalysis(BaseModel):
    """單支影片 LLM 分析結果 — 這是核心 schema"""
    video_id: str
    title: str
    channel_name: str
    published_at: datetime
    url: str
    summary_short: str                          # 50 字內短摘要
    summary_long: str                           # 300 字內長摘要
    bullet_points: list[str]                    # 3~10 條重點
    keywords: list[str]                         # 關鍵字
    topics: list[str]                           # 主題分類
    industries: list[str]                       # 提到的產業
    mentioned_tickers_or_assets: list[str]      # 提到的標的（個股/ETF/商品）
    macro_factors: list[str]                    # 提到的總經因素
    speaker_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    confidence_level: Literal["high", "medium", "low"]
    claims_explicit: list[str]                  # 講者明確提到的論點
    inferred_insights: list[str]                # 模型推論的觀察
    bullish_points: list[str]                   # 偏多論點
    bearish_points: list[str]                   # 偏空論點
    actionable_watchlist: list[str]             # 值得追蹤的標的
    risk_warnings: list[str]                    # 風險提醒
    notable_quotes: list[str]                   # 重要原文摘錄

class DailyTrendAnalysis(BaseModel):
    """每日趨勢彙整"""
    date: str
    total_videos_analyzed: int
    common_topics: list[str]
    top_industries: list[str]
    top_assets: list[str]
    overall_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    sentiment_breakdown: dict[str, int]         # {"bullish": 3, "bearish": 1, ...}
    high_frequency_keywords: list[str]
    strong_conviction_items: list[str]          # 講者語氣強烈的主題
    recommended_watchlist: list[str]            # 今日值得追蹤 3~10 項
    risk_summary: list[str]
    daily_narrative: str                        # 200 字整體敘述

class WeeklyTrendAnalysis(BaseModel):
    """每週趨勢彙整"""
    week_start: str
    week_end: str
    total_videos_analyzed: int
    common_topics: list[str]
    top_industries: list[str]
    top_assets: list[str]
    overall_sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    sentiment_trend: str                        # 本週情緒變化趨勢描述
    high_frequency_keywords: list[str]
    strong_conviction_items: list[str]
    recommended_watchlist: list[str]
    risk_summary: list[str]
    weekly_narrative: str                       # 本週整體敘述

class ProcessingStatus(BaseModel):
    video_id: str
    status: Literal["pending", "transcript_done", "analysis_done", "reported", "failed"]
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_time_seconds: float | None = None
```

#### Step 1.6 — `database.py`
用 SQLite 實作以下功能：
- `init_db()` — 建立 `videos` 表（存 metadata + 處理狀態）與 `processing_log` 表
- `is_video_processed(video_id) -> bool`
- `save_video_metadata(metadata: VideoMetadata)`
- `update_video_status(video_id, status, error_message=None)`
- `get_videos_by_status(status) -> list`
- `get_videos_for_date(date) -> list`
- `get_videos_for_week(week_start, week_end) -> list`
- 所有方法都要有完整的 error handling 與 logging

#### Step 1.7 — `utils/retry.py`
實作一個 `@retry` decorator，支援：
- `max_retries: int`
- `delay: float`（秒）
- `backoff_factor: float`
- `exceptions: tuple`（哪些 exception 要 retry）
- 每次 retry 都要 log warning

#### Step 1.8 — `utils/text_processing.py`
實作文字清洗函式：
- `clean_transcript(raw_text: str) -> str` — 移除多餘空白、重複行、時間戳記等
- `chunk_text(text: str, max_chars: int, overlap: int) -> list[str]` — 將長文切塊，chunk 之間有 overlap

---

### Phase 2：影片抓取模組 (`ingestion/`)

#### Step 2.1 — `channel_checker.py`
- 用 YouTube Data API v3 的 `search().list()` 檢查頻道是否有新影片
- 方法 `get_new_videos(channel_id, since_date) -> list[VideoMetadata]`
- 過濾條件：`publishedAfter`，`type=video`，`order=date`
- 使用 `@retry` decorator
- 每個 API call 都要 log

#### Step 2.2 — `metadata_fetcher.py`
- 用 YouTube Data API v3 的 `videos().list()` 取得完整 metadata
- 方法 `fetch_metadata(video_id) -> VideoMetadata`
- 取得 `snippet`（標題、描述、發布時間）與 `contentDetails`（時長）

#### Step 2.3 — `subtitle_fetcher.py`
- 用 `yt-dlp` 抓字幕（優先自動字幕、其次自動產生字幕）
- 方法 `fetch_subtitle(video_id, language) -> str | None`
- 若無字幕，方法 `download_audio(video_id, output_dir) -> Path` 下載音訊
- 音訊格式：mp3 或 m4a，限制品質以節省空間
- 實作方法 `get_transcript(video_id, language) -> TranscriptResult`：整合字幕或 STT 流程

---

### Phase 3：語音轉文字模組 (`transcription/`)

#### Step 3.1 — `base.py`
定義 abstract base class：
```python
from abc import ABC, abstractmethod

class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str) -> str:
        """將音訊檔轉成文字"""
        pass
```

#### Step 3.2 — `whisper_provider.py`
實作 `WhisperSTTProvider(STTProvider)`：
- 使用 OpenAI Whisper API
- 處理大檔案：若音訊超過 25MB，自動切割
- 使用 `@retry` decorator

#### Step 3.3 — `processor.py`
- 方法 `process_transcript(raw_text, source) -> TranscriptResult`
- 呼叫 `clean_transcript` 清洗文字
- 計算字數、字元數

---

### Phase 4：LLM 分析模組 (`analysis/`)

#### Step 4.1 — `base.py`
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, prompt: str, system_prompt: str) -> str:
        """送出 prompt 並取得回應"""
        pass
```

#### Step 4.2 — `claude_provider.py`
實作 `ClaudeLLMProvider(LLMProvider)`：
- 使用 `anthropic` SDK
- model: `claude-sonnet-4-20250514`
- `max_tokens`: 8192
- 使用 `@retry` decorator（retry on API errors / rate limits）
- log token usage

#### Step 4.3 — `prompts.py`
定義所有 prompt templates。這是系統最關鍵的部分，prompt 品質直接影響分析結果。

**單支影片分析 prompt（`VIDEO_ANALYSIS_PROMPT`）**：

System prompt 要求 LLM：
1. 你是一位專業的財經分析師助理，專精於投資、總經、產業分析
2. 你的任務是分析 YouTube 財經影片的逐字稿，產出結構化分析結果
3. 嚴格區分「講者明確提到的內容」（放在 `claims_explicit`）與「你的推論」（放在 `inferred_insights`）。若不確定，歸類為推論
4. 回傳格式必須是純 JSON，完全符合給定的 schema，不要加任何 markdown 標記或額外文字
5. 所有分析都不構成投資建議
6. 語言：根據影片語言回應（中文影片用繁體中文、英文影片用英文）

User prompt 模板：
```
請分析以下影片逐字稿：

影片標題：{title}
頻道名稱：{channel_name}
發布時間：{published_at}
影片網址：{url}
影片說明：{description}

逐字稿內容：
{transcript}

請依照以下 JSON schema 回傳分析結果：
{json_schema}

注意事項：
- summary_short: 50 字以內
- summary_long: 300 字以內
- bullet_points: 3~10 條最重要的重點
- speaker_sentiment: 判斷講者整體偏多(bullish)、偏空(bearish)、中性(neutral)、混合(mixed)
- confidence_level: 你對這份分析的信心程度
- claims_explicit: 只放講者明確說出的論點
- inferred_insights: 只放你的推論，標註為推論
- notable_quotes: 擷取逐字稿中最重要的原文片段（每段不超過 50 字）
```

**每日趨勢分析 prompt（`DAILY_TREND_PROMPT`）**：

給 LLM 當天所有影片的分析結果 JSON，要求：
1. 歸納今日多支影片共同提到的主題
2. 找出最常被提及的產業和投資商品
3. 判斷今日整體市場情緒偏向
4. 分辨「高頻出現」與「強烈語氣」，分開列出
5. 推薦今日值得追蹤的 3~10 個主題或標的
6. 產出 200 字整體敘述
7. 回傳格式必須是純 JSON，符合 `DailyTrendAnalysis` schema

**每週趨勢分析 prompt（`WEEKLY_TREND_PROMPT`）**：

給 LLM 當週所有影片的分析結果 JSON，要求：
1. 歸納本週多支影片共同提到的主題
2. 找出最常被提及的產業和投資商品
3. 判斷本週整體市場情緒偏向及變化趨勢
4. 分辨「高頻出現」與「強烈語氣」，分開列出
5. 推薦本週值得追蹤的主題或標的
6. 與上週相比的變化觀察
7. 產出 300 字整體敘述
8. 回傳格式必須是純 JSON，符合 `WeeklyTrendAnalysis` schema

**Chunked 分析 prompt（`PRELIMINARY_SUMMARY_PROMPT`）**：

當逐字稿太長需要分段時，先對每個 chunk 做初步摘要，再合併所有摘要進行完整分析。

#### Step 4.4 — `schema_validator.py`
- 方法 `validate_analysis(raw_json: str) -> VideoAnalysis` — 解析 LLM 回傳的 JSON 並用 Pydantic model 驗證
- 方法 `validate_trend(raw_json: str) -> DailyTrendAnalysis`
- 方法 `validate_weekly_trend(raw_json: str) -> WeeklyTrendAnalysis`
- 若 JSON 格式錯誤，嘗試修復（去掉 markdown 標記、修復常見格式問題）
- 若修復失敗，raise 明確的 `SchemaValidationError` 並包含詳細錯誤訊息
- 使用 Pydantic 的 `model_validate_json` 或 `model_validate`

#### Step 4.5 — `video_analyzer.py`
class `VideoAnalyzerService`：
- `analyze_video(metadata: VideoMetadata, transcript: TranscriptResult) -> VideoAnalysis`
- 處理長文 chunking 邏輯：
  1. 若 transcript 長度 < `MAX_TRANSCRIPT_CHARS`，直接分析
  2. 若超過，先用 `PRELIMINARY_SUMMARY_PROMPT` 分段摘要，再合併分析
- 分析完成後將結果儲存為 JSON 檔（存到 `data/analysis/`）
- 使用 `@retry` decorator
- 完整 logging（開始、結束、耗時、token usage）

#### Step 4.6 — `trend_analyzer.py`
class `TrendAnalyzerService`：
- `analyze_daily_trend(analyses: list[VideoAnalysis], date: str) -> DailyTrendAnalysis`
- `analyze_weekly_trend(analyses: list[VideoAnalysis], week_start: str, week_end: str) -> WeeklyTrendAnalysis`
- 將當天/當週所有影片分析結果打包送給 LLM
- 儲存趨勢分析結果 JSON

---

### Phase 5：報告產生模組 (`reporting/`)

#### Step 5.1 — HTML 模板設計

所有 HTML 模板必須遵循以下設計規範：
- **內嵌 CSS**（email 相容，不用外部 CSS）
- 配色：深藍 `#1a365d` 為主色、白色背景、淺灰 `#f7f8fa` 區塊背景
- 字體：`-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- 最大寬度 `700px`，置中
- 報告頂部固定顯示 disclaimer：「⚠️ 以下為 AI 分析整理，不構成投資建議。請獨立判斷，審慎評估風險。」
- 所有 `inferred_insights` 區塊需加上標籤「🤖 模型推論」
- 所有 `claims_explicit` 區塊需加上標籤「🎯 講者明確提到」

**`individual_report.html.j2`**：
- 標題區：影片標題、頻道、日期、連結
- 摘要區：短摘要 + 長摘要
- 重點清單：bullet_points
- 兩欄卡片：偏多觀點 / 偏空觀點
- 關鍵字標籤雲（用 inline-block span 模擬）
- 產業與標的表格
- 總經因素列表
- 講者明確論點 vs 模型推論（分開顯示，明確標記）
- 追蹤清單
- 風險提醒（紅色邊框卡片）
- 重要原文摘錄（引用樣式）
- 頁尾 disclaimer

**`daily_digest.html.j2`**：
- 標題區：日期 + 處理影片數
- 今日概述：`daily_narrative`
- 今日市場情緒（用色彩標記 bullish/bearish/neutral）
- 高頻關鍵字
- 熱門產業排行
- 熱門標的排行
- 今日推薦追蹤清單
- 強烈語氣項目
- 風險摘要
- 各影片摘要卡片（每支影片一張小卡，含標題、頻道、短摘要、情緒標記）
- 頁尾 disclaimer

**`weekly_digest.html.j2`**：
- 標題區：週期間 + 處理影片數
- 本週概述：`weekly_narrative`
- 本週市場情緒及趨勢變化
- 高頻關鍵字
- 熱門產業排行
- 熱門標的排行
- 本週推薦追蹤清單
- 強烈語氣項目
- 風險摘要
- 每日摘要回顧（每天一張小卡，含當天的關鍵資訊）
- 頁尾 disclaimer

#### Step 5.2 — `report_generator.py`
class `ReportGenerator`：
- `generate_individual_report(analysis: VideoAnalysis) -> Path` — 產生單支影片 HTML 報告
- `generate_daily_digest(trend: DailyTrendAnalysis, analyses: list[VideoAnalysis], date: str) -> Path` — 產生每日彙整 HTML 報告
- 報告存放到 `data/reports/{date}/`
- 使用 Jinja2 載入模板、render HTML、寫入檔案

#### Step 5.3 — `weekly_report_generator.py`
class `WeeklyReportGenerator`：
- `generate_weekly_digest(trend: WeeklyTrendAnalysis, daily_trends: list[DailyTrendAnalysis], date_range: str) -> Path` — 產生每週彙整 HTML 報告
- 報告存放到 `data/reports/weekly/`

---

### Phase 6：Email 寄送模組 (`delivery/`)

#### Step 6.1 — `email_sender.py`
class `EmailSender`：
- `send_daily_digest(html_path: Path, date: str, attach_individual: bool = False)`
- `send_weekly_digest(html_path: Path, week_range: str)`
- Email 主旨格式：`[財經日報] {date} — {overall_sentiment} — 共 {n} 支影片分析`
- 週報主旨格式：`[財經週報] {week_range} — 本週趨勢分析`
- 支援多個收件人（從設定讀取）
- HTML 內容直接放在 email body
- 若 `attach_individual=True`，將個別報告作為附件
- 發送失敗要 log error，但不要 raise（不影響主流程）
- 使用 `@retry` decorator（retry 2 次）

---

### Phase 7：主流程 (`main.py`)

#### Step 7.1 — CLI 進入點

使用 `argparse` 提供以下命令：

```bash
# 執行每日分析（預設行為）
yt-finance-analyzer run --date 2024-01-15

# 只抓取新影片（不分析）
yt-finance-analyzer fetch

# 只對已抓取的影片進行分析
yt-finance-analyzer analyze --date 2024-01-15

# 只產生報告
yt-finance-analyzer report --date 2024-01-15

# 產生週報
yt-finance-analyzer weekly-report --week-of 2024-01-15

# 只寄送 email
yt-finance-analyzer send --date 2024-01-15

# 寄送週報
yt-finance-analyzer send-weekly --week-of 2024-01-15

# 查看處理狀態
yt-finance-analyzer status --date 2024-01-15
```

#### Step 7.2 — 主流程邏輯（`run` command）

```python
def run_daily_pipeline(date: str):
    """
    每日主流程：
    1. 讀取設定與頻道清單
    2. 對每個頻道檢查新影片
    3. 過濾已處理的影片
    4. 限制每日最大處理數
    5. 對每支影片依序：
       a. 抓取 metadata
       b. 抓取字幕 / STT
       c. LLM 分析
       d. 儲存分析結果
       e. 產生 individual report
       - 任一步驟失敗：log error, 標記該影片為 failed, 繼續下一支
    6. 彙整趨勢分析
    7. 產生 daily digest report
    8. 寄送 email
    9. 清理暫存音訊檔
    """
```

每個步驟都要：
- log 開始與結束
- 記錄耗時
- 捕捉所有 exception，單支影片失敗不影響其他影片

#### Step 7.3 — 週報流程邏輯（`weekly-report` command）

```python
def run_weekly_pipeline(week_of_date: str):
    """
    每週主流程：
    1. 計算該週的起始與結束日期（週一到週日）
    2. 從資料庫取得該週所有已分析的影片
    3. 載入所有影片的分析結果 JSON
    4. 載入該週每天的 daily trend 分析
    5. LLM 進行週趨勢彙整分析
    6. 產生 weekly digest report
    7. 寄送週報 email
    """
```

---

## 重要注意事項

### 程式碼品質
- 每個檔案開頭加 module docstring 說明此模組的職責
- 每個 class 和 public method 都要有 docstring
- 關鍵邏輯段落加上 inline comment 說明意圖
- 使用 type hints
- 避免任何 hardcoded 值，全部走設定

### Logging 規範
- 使用 `logging.getLogger(__name__)` 取得 logger
- 格式：`%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- 在 `main.py` 中統一設定 root logger level
- 關鍵節點的 log：
  - 每支影片處理開始 / 結束（含耗時）
  - API 呼叫前後
  - 錯誤與 retry
  - 每日流程的 summary（成功 N 支、失敗 N 支、跳過 N 支）

### 錯誤處理
- 定義自訂 exception classes（在 `models.py` 或獨立的 `exceptions.py`）：
  - `VideoFetchError`
  - `TranscriptionError`
  - `AnalysisError`
  - `SchemaValidationError`
  - `ReportGenerationError`
  - `EmailSendError`
- 主流程中捕捉這些 exception，log 後繼續

### 成本控制
- 逐字稿超過 `MAX_TRANSCRIPT_CHARS` 時使用 chunking
- 先做 preliminary summary（便宜的步驟），再做深度分析
- 快取：分析結果存為 JSON，若已存在則跳過
- 設定 `MAX_VIDEOS_PER_DAY` 限制

---

## 最後要求

1. 請完整實作所有檔案，不要留 placeholder 或 `TODO`
2. 所有程式碼都要能正確執行（假設 API keys 正確）
3. 每寫完一個 Phase 之後，確認與前面的 Phase 的接口一致
4. 完成後，在 `README.md` 中寫出：
   - 專案簡介
   - 安裝步驟（`pip install -e .`）
   - 設定說明（環境變數 + channels.yaml）
   - 使用方式（CLI commands）
   - cron 排程設定範例
   - 目錄結構說明
   - 注意事項與限制
