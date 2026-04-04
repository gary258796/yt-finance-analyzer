"""文字清洗與分段工具。"""

import re


def clean_transcript(raw_text: str) -> str:
    """清洗逐字稿：移除多餘空白、重複行、時間戳記等。

    Args:
        raw_text: 原始逐字稿文字。

    Returns:
        清洗後的文字。
    """
    if not raw_text:
        return ""

    text = raw_text

    # 移除常見的時間戳記格式 (e.g., [00:01:23], 00:01:23, (00:01:23))
    text = re.sub(r"[\[\(]?\d{1,2}:\d{2}(?::\d{2})?[\]\)]?\s*", "", text)

    # 移除 HTML 標籤
    text = re.sub(r"<[^>]+>", "", text)

    # 移除重複行
    lines = text.splitlines()
    seen: set[str] = set()
    unique_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            unique_lines.append(stripped)

    text = "\n".join(unique_lines)

    # 合併多餘空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def chunk_text(text: str, max_chars: int, overlap: int = 200) -> list[str]:
    """將長文切塊，chunk 之間有 overlap。

    以段落邊界為優先切割點，若單一段落超過 max_chars 則在句號處切割。

    Args:
        text: 要切塊的文字。
        max_chars: 每塊最大字元數。
        overlap: chunk 之間的重疊字元數。

    Returns:
        切塊後的文字列表。
    """
    if not text or max_chars <= 0:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + max_chars

        if end >= len(text):
            chunks.append(text[start:])
            break

        # 尋找最佳切割點：優先段落邊界，其次句號
        chunk = text[start:end]

        # 從尾端往前找段落邊界
        split_pos = chunk.rfind("\n\n")
        if split_pos == -1 or split_pos < max_chars // 2:
            # 找不到段落邊界，嘗試句號（中英文）
            for sep in ("。", ".", "！", "!", "？", "?"):
                pos = chunk.rfind(sep)
                if pos > max_chars // 2:
                    split_pos = pos + len(sep)
                    break

        if split_pos == -1 or split_pos < max_chars // 2:
            # 都找不到好的切割點，直接切
            split_pos = max_chars

        chunks.append(text[start : start + split_pos])

        # 下一塊起始位置要扣掉 overlap
        start = start + split_pos - overlap
        if start < 0:
            start = 0

    return chunks
