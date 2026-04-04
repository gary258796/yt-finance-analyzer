"""語音轉文字抽象介面定義。"""

from abc import ABC, abstractmethod
from pathlib import Path


class STTProvider(ABC):
    """語音轉文字服務的抽象基底類別。"""

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str) -> str:
        """將音訊檔轉成文字。

        Args:
            audio_path: 音訊檔案路徑。
            language: 語言代碼。

        Returns:
            轉錄後的文字內容。
        """
