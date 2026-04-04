"""可設定的 retry decorator，支援指數退避。"""

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Retry decorator，遇到指定 exception 時自動重試。

    Args:
        max_retries: 最大重試次數。
        delay: 首次重試等待秒數。
        backoff_factor: 每次重試的等待倍數。
        exceptions: 需要 retry 的 exception 類型。
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(1, max_retries + 2):  # 1 次正常 + max_retries 次重試
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt > max_retries:
                        logger.error(
                            "%s 重試 %d 次後仍然失敗: %s",
                            func.__name__,
                            max_retries,
                            exc,
                        )
                        raise
                    logger.warning(
                        "%s 第 %d/%d 次重試（等待 %.1f 秒）: %s",
                        func.__name__,
                        attempt,
                        max_retries,
                        current_delay,
                        exc,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_factor

            # 理論上不會到這裡，但為了 type safety
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
