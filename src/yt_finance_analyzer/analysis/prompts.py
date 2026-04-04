"""所有 LLM prompt templates。這是系統最關鍵的部分，prompt 品質直接影響分析結果。"""

# ---------------------------------------------------------------------------
# 單支影片分析
# ---------------------------------------------------------------------------

VIDEO_ANALYSIS_SYSTEM_PROMPT = """你是一位專業的財經分析師助理，專精於投資、總經、產業分析。

你的任務是分析 YouTube 財經影片的逐字稿，產出結構化分析結果。

重要規則：
1. 嚴格區分「講者明確提到的內容」（放在 claims_explicit）與「你的推論」（放在 inferred_insights）。若不確定，歸類為推論。
2. 回傳格式必須是純 JSON，完全符合給定的 schema，不要加任何 markdown 標記或額外文字。
3. 所有分析都不構成投資建議。
4. 語言：根據影片語言回應（中文影片用繁體中文、英文影片用英文）。
5. 不要在 JSON 之外輸出任何文字。"""

VIDEO_ANALYSIS_PROMPT = """請分析以下影片逐字稿：

影片標題：{title}
頻道名稱：{channel_name}
發布時間：{published_at}
影片網址：{url}
影片說明：{description}

逐字稿內容：
{transcript}

請依照以下 JSON schema 回傳分析結果：
{{
  "video_id": "{video_id}",
  "title": "{title}",
  "channel_name": "{channel_name}",
  "published_at": "{published_at}",
  "url": "{url}",
  "summary_short": "50 字以內短摘要",
  "summary_long": "300 字以內長摘要",
  "bullet_points": ["3~10 條最重要的重點"],
  "keywords": ["關鍵字列表"],
  "topics": ["主題分類"],
  "industries": ["提到的產業"],
  "mentioned_tickers_or_assets": ["提到的標的（個股/ETF/商品）"],
  "macro_factors": ["提到的總經因素"],
  "speaker_sentiment": "bullish|bearish|neutral|mixed",
  "confidence_level": "high|medium|low",
  "claims_explicit": ["講者明確說出的論點"],
  "inferred_insights": ["模型推論的觀察"],
  "bullish_points": ["偏多論點"],
  "bearish_points": ["偏空論點"],
  "actionable_watchlist": ["值得追蹤的標的"],
  "risk_warnings": ["風險提醒"],
  "notable_quotes": ["重要原文摘錄，每段不超過 50 字"]
}}

注意事項：
- summary_short: 50 字以內
- summary_long: 300 字以內
- bullet_points: 3~10 條最重要的重點
- speaker_sentiment: 判斷講者整體偏多(bullish)、偏空(bearish)、中性(neutral)、混合(mixed)
- confidence_level: 你對這份分析的信心程度
- claims_explicit: 只放講者明確說出的論點
- inferred_insights: 只放你的推論，標註為推論
- notable_quotes: 擷取逐字稿中最重要的原文片段（每段不超過 50 字）"""

# ---------------------------------------------------------------------------
# 每日趨勢分析
# ---------------------------------------------------------------------------

DAILY_TREND_SYSTEM_PROMPT = """你是一位專業的財經分析師助理，負責彙整當天多支 YouTube 財經影片的分析結果。

重要規則：
1. 回傳格式必須是純 JSON，符合給定的 schema，不要加任何 markdown 標記或額外文字。
2. 所有分析都不構成投資建議。
3. 使用繁體中文回應。
4. 不要在 JSON 之外輸出任何文字。"""

DAILY_TREND_PROMPT = """以下是今天 ({date}) 所有影片的分析結果 JSON：

{analyses_json}

請根據以上分析結果，產出今日趨勢彙整。要求：
1. 歸納今日多支影片共同提到的主題
2. 找出最常被提及的產業和投資商品
3. 判斷今日整體市場情緒偏向
4. 分辨「高頻出現」與「強烈語氣」，分開列出
5. 推薦今日值得追蹤的 3~10 個主題或標的
6. 產出 200 字整體敘述

回傳 JSON schema：
{{
  "date": "{date}",
  "total_videos_analyzed": {total_videos},
  "common_topics": ["共同主題"],
  "top_industries": ["熱門產業"],
  "top_assets": ["熱門標的"],
  "overall_sentiment": "bullish|bearish|neutral|mixed",
  "sentiment_breakdown": {{"bullish": 0, "bearish": 0, "neutral": 0, "mixed": 0}},
  "high_frequency_keywords": ["高頻關鍵字"],
  "strong_conviction_items": ["講者語氣強烈的主題"],
  "recommended_watchlist": ["今日值得追蹤 3~10 項"],
  "risk_summary": ["風險摘要"],
  "daily_narrative": "200 字整體敘述"
}}"""

# ---------------------------------------------------------------------------
# 每週趨勢分析
# ---------------------------------------------------------------------------

WEEKLY_TREND_SYSTEM_PROMPT = """你是一位專業的財經分析師助理，負責彙整本週多支 YouTube 財經影片的分析結果。

重要規則：
1. 回傳格式必須是純 JSON，符合給定的 schema，不要加任何 markdown 標記或額外文字。
2. 所有分析都不構成投資建議。
3. 使用繁體中文回應。
4. 不要在 JSON 之外輸出任何文字。"""

WEEKLY_TREND_PROMPT = """以下是本週 ({week_start} ~ {week_end}) 所有影片的分析結果 JSON：

{analyses_json}

請根據以上分析結果，產出本週趨勢彙整。要求：
1. 歸納本週多支影片共同提到的主題
2. 找出最常被提及的產業和投資商品
3. 判斷本週整體市場情緒偏向及變化趨勢
4. 分辨「高頻出現」與「強烈語氣」，分開列出
5. 推薦本週值得追蹤的主題或標的
6. 與上週相比的變化觀察
7. 產出 300 字整體敘述

回傳 JSON schema：
{{
  "week_start": "{week_start}",
  "week_end": "{week_end}",
  "total_videos_analyzed": {total_videos},
  "common_topics": ["共同主題"],
  "top_industries": ["熱門產業"],
  "top_assets": ["熱門標的"],
  "overall_sentiment": "bullish|bearish|neutral|mixed",
  "sentiment_trend": "本週情緒變化趨勢描述",
  "high_frequency_keywords": ["高頻關鍵字"],
  "strong_conviction_items": ["講者語氣強烈的主題"],
  "recommended_watchlist": ["本週值得追蹤"],
  "risk_summary": ["風險摘要"],
  "weekly_narrative": "300 字整體敘述"
}}"""

# ---------------------------------------------------------------------------
# Chunked 分析（長逐字稿初步摘要）
# ---------------------------------------------------------------------------

PRELIMINARY_SUMMARY_SYSTEM_PROMPT = """你是一位專業的財經分析師助理。你的任務是對一段逐字稿片段進行初步摘要。

重要規則：
1. 回傳格式必須是純 JSON，不要加任何 markdown 標記或額外文字。
2. 使用與逐字稿相同的語言回應。
3. 不要在 JSON 之外輸出任何文字。"""

PRELIMINARY_SUMMARY_PROMPT = """這是一段較長影片逐字稿的第 {chunk_index}/{total_chunks} 段。

影片標題：{title}
頻道名稱：{channel_name}

逐字稿片段：
{chunk_text}

請對此片段進行初步摘要，回傳以下 JSON：
{{
  "summary": "此片段的重點摘要（200 字以內）",
  "key_points": ["此片段的重要論點"],
  "mentioned_assets": ["此片段提到的標的"],
  "sentiment_hints": "此片段的情緒傾向（bullish/bearish/neutral/mixed）"
}}"""
