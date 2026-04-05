# YouTube 財經影片自動分析系統

每天自動抓取指定 YouTube 頻道的新影片，將內容轉為文字，透過 LLM 進行結構化財經分析，產出 HTML 報告並以 Email 寄送。

## 系統流程

```
頻道設定 → YouTube API 檢查新片 → 取得字幕/音訊 → 語音轉文字（Whisper）
→ LLM 結構化分析（Claude）→ HTML 報告（Jinja2）→ Email 寄送
```

每支影片獨立處理，單一失敗不影響其他影片。

## 安裝

需要 Python 3.11+。

```bash
git clone <repo-url>
cd yt-finance-analyzer
pip install -e .
```

安裝完成後即可使用 `yt-finance-analyzer` 命令。

## 設定

### 環境變數

複製範本並填入實際值：

```bash
cp .env.example .env
```

| 變數 | 說明 | 必填 |
|------|------|------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 金鑰 | 是 |
| `ANTHROPIC_API_KEY` | Anthropic API 金鑰（Claude LLM 分析） | 是 |
| `OPENAI_API_KEY` | OpenAI API 金鑰（Whisper 語音轉文字，僅無字幕時需要） | 視情況 |
| `SMTP_HOST` | SMTP 伺服器位址（預設 `smtp.gmail.com`） | 寄信時需要 |
| `SMTP_PORT` | SMTP 埠號（預設 `587`） | 寄信時需要 |
| `SMTP_USERNAME` | SMTP 帳號 | 寄信時需要 |
| `SMTP_PASSWORD` | SMTP 密碼（Gmail 請用應用程式密碼） | 寄信時需要 |
| `EMAIL_FROM` | 寄件人地址 | 寄信時需要 |
| `EMAIL_TO` | 收件人地址，多人以逗號分隔 | 寄信時需要 |
| `MAX_VIDEOS_PER_DAY` | 每日最大處理影片數（預設 `20`） | 否 |
| `MAX_TRANSCRIPT_CHARS` | 逐字稿最大字元數，超過則分段處理（預設 `50000`） | 否 |
| `DATA_DIR` | 資料儲存目錄（預設 `./data`） | 否 |

### 頻道設定

cp config/channels.example.yaml config/channels.yaml
編輯 `config/channels.yaml`，加入要追蹤的 YouTube 頻道：

```yaml
channels:
  - channel_id: "UC_CHANNEL_ID"
    handle: "@channel_handle"    # channel_id 和 handle 至少填一個
    name: "頻道名稱"
    language: "zh-TW"            # zh-TW 或 en
    enabled: true                # false 可暫時停用
```

## 使用方式

所有命令皆支援 `--verbose`（`-v`）旗標以開啟 DEBUG 日誌。

### 完整每日管線

抓取 → 分析 → 報告 → 寄送，一次完成：

```bash
yt-finance-analyzer run --date 2024-01-15
yt-finance-analyzer run                      # 預設今天
```

### 個別步驟

可單獨執行管線中的各個階段：

```bash
# 只抓取新影片（存入資料庫，不分析）
yt-finance-analyzer fetch

# 只對已抓取的影片進行 LLM 分析
yt-finance-analyzer analyze --date 2024-01-15

# 只產生 HTML 報告（需先有分析結果）
yt-finance-analyzer report --date 2024-01-15

# 只寄送每日報告 email（需先有報告檔案）
yt-finance-analyzer send --date 2024-01-15
```

### 週報

```bash
# 產生指定日期所在那一週的週報（週一~週日）
yt-finance-analyzer weekly-report --week-of 2024-01-15

# 寄送週報 email
yt-finance-analyzer send-weekly --week-of 2024-01-15
```

### 查看狀態

```bash
yt-finance-analyzer status --date 2024-01-15
```

顯示該日所有影片的處理狀態（`pending` → `transcript_done` → `analysis_done` → `reported` / `failed`）。

## 命令總覽

| 命令 | 參數 | 說明 |
|------|------|------|
| `run` | `--date YYYY-MM-DD` | 執行完整每日管線（預設今天） |
| `fetch` | 無 | 抓取所有啟用頻道的新影片 |
| `analyze` | `--date YYYY-MM-DD` | 對指定日期影片做 LLM 分析 |
| `report` | `--date YYYY-MM-DD` | 產生 HTML 報告 |
| `weekly-report` | `--week-of YYYY-MM-DD` | 產生該週的週報（預設今天） |
| `send` | `--date YYYY-MM-DD` | 寄送每日報告 email |
| `send-weekly` | `--week-of YYYY-MM-DD` | 寄送週報 email |
| `status` | `--date YYYY-MM-DD` | 查看影片處理狀態 |

## 排程（Cron）

可搭配 cron 實現每日自動執行：

```cron
# 每天早上 8:00 執行完整管線
0 8 * * * cd /path/to/yt-finance-analyzer && yt-finance-analyzer run >> /var/log/yt-finance.log 2>&1

# 每週一早上 9:00 產生並寄送週報
0 9 * * 1 cd /path/to/yt-finance-analyzer && yt-finance-analyzer weekly-report && yt-finance-analyzer send-weekly --week-of "$(date -v-1d +\%Y-\%m-\%d)" >> /var/log/yt-finance-weekly.log 2>&1
```

## 目錄結構

```
yt-finance-analyzer/
├── pyproject.toml              # 專案設定與 dependencies
├── .env.example                # 環境變數範本
├── config/
│   └── channels.yaml           # YouTube 頻道設定
├── src/yt_finance_analyzer/
│   ├── main.py                 # CLI 進入點
│   ├── config.py               # 設定管理
│   ├── database.py             # SQLite 資料庫
│   ├── models.py               # 資料模型與例外類別
│   ├── ingestion/              # 影片抓取（YouTube API + yt-dlp）
│   ├── transcription/          # 語音轉文字（Whisper API）
│   ├── analysis/               # LLM 分析（Claude API）
│   ├── reporting/              # HTML 報告產生（Jinja2）
│   ├── delivery/               # Email 寄送（SMTP）
│   └── utils/                  # retry decorator、文字處理
└── data/                       # 執行時產生（gitignore）
    ├── db/                     # SQLite 資料庫
    ├── transcripts/            # 逐字稿
    ├── analysis/               # 分析結果 JSON
    ├── reports/                # HTML 報告
    └── audio/                  # 暫存音訊檔（處理後自動清除）
```

## 注意事項

- **API 費用**：每次分析會呼叫 Claude API（逐字稿過長時會分段，增加呼叫次數）。Whisper API 僅在影片無字幕時使用。系統透過快取機制避免重複分析。
- **Gmail SMTP**：需使用[應用程式密碼](https://support.google.com/accounts/answer/185833)，不能用帳號密碼。
- **語言**：中文（zh-TW）影片的分析結果為繁體中文，英文影片為英文。
- **報告聲明**：所有報告皆含 AI 分析免責聲明，模型推論與講者明確論點分開標示。
- **目前 Workflow**：無法成功讓 github workflow 透過 cookies.txt 取得字幕。 待解決。