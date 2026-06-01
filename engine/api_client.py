"""DeepSeek API client with retry and cost estimation."""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
MAX_TOKENS = 8192
TIMEOUT = 300
MAX_RETRIES = 3


class DeepSeekClient:
    """OpenAI-compatible wrapper for DeepSeek API."""

    def __init__(self, api_key: str, base_url: str = DEEPSEEK_BASE_URL):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0

    @property
    def total_cost(self) -> float:
        """Estimated total cost in CNY."""
        return (
            self._total_prompt_tokens / 1_000_000 * 1.0
            + self._total_completion_tokens / 1_000_000 * 2.0
        )

    def chat(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: int = MAX_TOKENS,
        retries: int = MAX_RETRIES,
    ) -> Optional[str]:
        """Send a chat request with retry logic. Returns response text or None."""
        messages = [{"role": "user", "content": prompt}]

        for attempt in range(1, retries + 1):
            try:
                logger.info(f"  API call... (attempt {attempt}/{retries})")
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=TIMEOUT,
                )
                content = resp.choices[0].message.content
                usage = resp.usage

                if usage:
                    self._total_prompt_tokens += usage.prompt_tokens
                    self._total_completion_tokens += usage.completion_tokens
                    cost = (
                        usage.prompt_tokens / 1_000_000 * 1.0
                        + usage.completion_tokens / 1_000_000 * 2.0
                    )
                    logger.info(
                        f"  API OK (in: {usage.prompt_tokens:,} tok, "
                        f"out: {usage.completion_tokens:,} tok, ¥{cost:.4f})"
                    )

                return content

            except Exception as e:
                msg = str(e).lower()
                retryable = any(k in msg for k in [
                    "rate", "throttle", "server", "timeout",
                    "503", "502", "429", "connection",
                ])
                if attempt < retries and retryable:
                    wait = 2 ** attempt
                    logger.warning(f"  Retryable error: {str(e)[:100]}")
                    logger.info(f"  Waiting {wait}s...")
                    time.sleep(wait)
                elif attempt < retries:
                    logger.warning(f"  API error: {str(e)[:100]}, retrying...")
                    time.sleep(3)
                else:
                    logger.error(f"  API final failure: {str(e)[:200]}")
                    return None
        return None
