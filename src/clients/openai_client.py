import os
import time
from typing import Optional
from src.models import LLMResponse
from src.scheduler import LLMClient


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI client not installed. Install with: pip install openai"
            )

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

        self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def call(self, prompt: str, max_output_token: int) -> LLMResponse:
        start_time = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output_token,
            temperature=self.temperature,
            timeout=self.timeout,
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        duration = time.time() - start_time

        from datetime import timedelta

        return LLMResponse(
            content=content,
            tokens_used=tokens_used,
            duration=timedelta(seconds=duration),
        )
