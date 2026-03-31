from abc import ABC, abstractmethod


class TokenEstimator(ABC):
    @abstractmethod
    def estimate(self, prompt, max_output_token):
        pass


class SimpleEstimator(TokenEstimator):
    def estimate(self, prompt, max_output_token):
        prompt_tokens = max(1, len(prompt) // 4)
        return prompt_tokens + max_output_token
