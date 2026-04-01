import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import openai
from typing import Optional
from src.models import LLMResponse
from src.scheduler import LLMClient


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

        if base_url:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=base_url)
        else:
            self.client = openai.OpenAI(api_key=self.api_key)

    def call(self, prompt: str, max_output_token: int) -> LLMResponse:
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_output_token,
                temperature=self.temperature,
                timeout=self.timeout,
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            duration = time.time() - start_time

            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                duration=duration,
            )
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {str(e)}")
