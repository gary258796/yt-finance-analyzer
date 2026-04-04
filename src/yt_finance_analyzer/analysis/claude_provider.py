"""Anthropic Claude LLM 實作。"""

import logging

import anthropic

from yt_finance_analyzer.analysis.base import LLMProvider
from yt_finance_analyzer.models import AnalysisError
from yt_finance_analyzer.utils.retry import retry

logger = logging.getLogger(__name__)


class ClaudeLLMProvider(LLMProvider):
    """使用 Anthropic Claude API 進行 LLM 分析。"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 8192,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @retry(
        max_retries=3,
        delay=5.0,
        backoff_factor=2.0,
        exceptions=(anthropic.APIError, anthropic.APIConnectionError),
    )
    def analyze(self, prompt: str, system_prompt: str) -> str:
        """送出 prompt 給 Claude API 並取得回應。

        Args:
            prompt: 使用者 prompt。
            system_prompt: 系統 prompt。

        Returns:
            Claude 回應的文字內容。

        Raises:
            AnalysisError: API 呼叫失敗。
        """
        logger.info("呼叫 Claude API (model: %s)", self._model)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            raise AnalysisError(f"Claude API 呼叫失敗: {exc}") from exc

        # 提取文字回應
        text_blocks = [
            block.text for block in response.content if block.type == "text"
        ]
        result = "\n".join(text_blocks)

        # Log token usage
        usage = response.usage
        logger.info(
            "Claude API 回應完成 (input: %d tokens, output: %d tokens)",
            usage.input_tokens,
            usage.output_tokens,
        )

        return result
