# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube financial video auto-analysis system. Fetches videos from configured YouTube channels daily, transcribes content, runs LLM-based structured financial analysis, generates HTML reports, and delivers via email. Written in Python (synchronous architecture), spec defined in `SPEC.md`.

## Build & Run Commands

```bash
# Install in dev mode
pip install -e .

# CLI entry point (after install)
yt-finance-analyzer run --date 2024-01-15    # Full daily pipeline
yt-finance-analyzer fetch                     # Fetch new videos only
yt-finance-analyzer analyze --date 2024-01-15 # Analyze fetched videos
yt-finance-analyzer report --date 2024-01-15  # Generate reports only
yt-finance-analyzer weekly-report --week-of 2024-01-15
yt-finance-analyzer send --date 2024-01-15    # Send email only
yt-finance-analyzer status --date 2024-01-15  # Check processing status

# Run tests
pytest tests/
pytest tests/test_models.py            # Single test file
pytest tests/test_models.py::test_name # Single test
```

## Architecture

### Pipeline Flow (daily)
Channels config -> Channel checker (YouTube API) -> Subtitle/audio fetch (yt-dlp) -> Transcription (Whisper API if no subtitles) -> LLM analysis (Claude API) -> HTML report (Jinja2) -> Email delivery (SMTP)

Each video is processed independently; a single failure does not block others.

### Module Layout (`src/yt_finance_analyzer/`)
- **main.py** — CLI entry point (`argparse`), orchestrates the pipeline
- **config.py** — `pydantic-settings` BaseSettings, reads `.env` + `config/channels.yaml`
- **database.py** — SQLite via `sqlite3`, tracks video processing status
- **models.py** — All Pydantic data models + custom exception classes
- **ingestion/** — YouTube Data API v3 (`google-api-python-client`) for channel checking/metadata, `yt-dlp` for subtitles/audio
- **transcription/** — Abstract `STTProvider` base class, OpenAI Whisper API implementation, transcript cleaning
- **analysis/** — Abstract `LLMProvider` base class, Anthropic Claude implementation, prompt templates in `prompts.py`, JSON schema validation via Pydantic
- **reporting/** — Jinja2 HTML report generation. Templates in `reporting/templates/` (individual, daily digest, weekly digest)
- **delivery/** — Email via `smtplib` + `email.mime`
- **utils/** — `@retry` decorator (configurable retries/backoff/exceptions), text chunking/cleaning

### Key Design Decisions
- Abstract interfaces for STT (`transcription/base.py`) and LLM (`analysis/base.py`) — new providers implement these
- Long transcripts use chunking: preliminary summaries per chunk, then merged for final analysis
- Analysis results cached as JSON in `data/analysis/` — skipped if already exists
- `data/` directory is runtime-only (gitignored): `db/`, `transcripts/`, `analysis/`, `reports/`, `audio/`
- All config via `.env` (pydantic-settings), no hardcoded values
- Video processing status tracked in SQLite: `pending` -> `transcript_done` -> `analysis_done` -> `reported` -> `failed`

## Tech Stack (strict)
- Python 3.11+, `pyproject.toml` (PEP 621), no `setup.py` or `requirements.txt`
- yt-dlp, google-api-python-client, anthropic SDK (Claude), openai SDK (Whisper), Jinja2, pydantic-settings, SQLite

## Conventions
- Every file starts with a module docstring
- All classes and public methods have docstrings
- Type hints everywhere
- Logging: `logging.getLogger(__name__)`, format `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- HTML reports use inline CSS (email-compatible), max-width 700px, deep blue `#1a365d` primary color
- All reports include AI disclaimer header; `inferred_insights` labeled as model inference, `claims_explicit` labeled as speaker-stated
- Language: Chinese (zh-TW) content stays in Traditional Chinese, English content stays in English
