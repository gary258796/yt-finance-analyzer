"""LLM 分析抽象介面定義。"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM 服務的抽象基底類別。"""

    @abstractmethod
    def analyze(self, prompt: str, system_prompt: str) -> str:
        """送出 prompt 並取得 LLM 回應。

        Args:
            prompt: 使用者 prompt。
            system_prompt: 系統 prompt。

        Returns:
            LLM 回應的文字內容。
        """
