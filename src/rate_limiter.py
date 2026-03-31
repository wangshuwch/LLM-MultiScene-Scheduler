import threading
import time
from datetime import datetime, timedelta
from .models import RateLimitState, SceneConfig


class SlidingWindowRateLimiter:
    def __init__(
        self,
        global_tpm,
        global_qpm,
        window_size_seconds=60,
        window_step_seconds=1,
    ):
        self._lock = threading.RLock()
        self.global_tpm = global_tpm
        self.global_qpm = global_qpm
        self.window_size_seconds = window_size_seconds
        self.window_step_seconds = window_step_seconds

        self.global_token_slots = [0] * window_size_seconds
        self.global_query_slots = [0] * window_size_seconds

        self.scene_token_slots = {}
        self.scene_query_slots = {}
        self.scene_configs = {}

        self.current_slot_index = 0
        self.last_update_time = time.time()
        self._window_start = datetime.now()
        self._window_end = datetime.now() + timedelta(seconds=window_size_seconds)

    def set_scene_config(self, config):
        with self._lock:
            self.scene_configs[config.scene_id] = config

    def _advance_window(self):
        now = time.time()
        seconds_passed = int(now - self.last_update_time)

        if seconds_passed <= 0:
            return

        for i in range(seconds_passed):
            slot_index = (self.current_slot_index + 1) % self.window_size_seconds
            self.global_token_slots[slot_index] = 0
            self.global_query_slots[slot_index] = 0

            for scene_id in self.scene_token_slots:
                self.scene_token_slots[scene_id][slot_index] = 0
                self.scene_query_slots[scene_id][slot_index] = 0

            self.current_slot_index = slot_index

        self.last_update_time = now
        self._window_start = datetime.now() - timedelta(seconds=self.window_size_seconds)
        self._window_end = datetime.now()

    def _get_global_tokens_used(self):
        return sum(self.global_token_slots)

    def _get_global_queries_used(self):
        return sum(self.global_query_slots)

    def _get_scene_tokens_used(self, scene_id):
        if scene_id not in self.scene_token_slots:
            return 0
        return sum(self.scene_token_slots[scene_id])

    def _get_scene_queries_used(self, scene_id):
        if scene_id not in self.scene_query_slots:
            return 0
        return sum(self.scene_query_slots[scene_id])

    def try_acquire(self, scene_id, tokens):
        with self._lock:
            self._advance_window()

            global_tokens = self._get_global_tokens_used()
            global_queries = self._get_global_queries_used()

            if global_tokens + tokens > self.global_tpm:
                return False
            if global_queries + 1 > self.global_qpm:
                return False

            if scene_id in self.scene_configs:
                scene_config = self.scene_configs[scene_id]
                scene_tokens = self._get_scene_tokens_used(scene_id)
                scene_queries = self._get_scene_queries_used(scene_id)

                if scene_config.scene_tpm > 0 and scene_tokens + tokens > scene_config.scene_tpm:
                    return False
                if scene_config.scene_qpm > 0 and scene_queries + 1 > scene_config.scene_qpm:
                    return False

            self.global_token_slots[self.current_slot_index] += tokens
            self.global_query_slots[self.current_slot_index] += 1

            if scene_id not in self.scene_token_slots:
                self.scene_token_slots[scene_id] = [0] * self.window_size_seconds
                self.scene_query_slots[scene_id] = [0] * self.window_size_seconds

            self.scene_token_slots[scene_id][self.current_slot_index] += tokens
            self.scene_query_slots[scene_id][self.current_slot_index] += 1

            return True

    def get_rate_limit_state(self):
        with self._lock:
            self._advance_window()

            scene_tpm_used = {}
            scene_qpm_used = {}

            for scene_id in self.scene_configs:
                scene_tpm_used[scene_id] = self._get_scene_tokens_used(scene_id)
                scene_qpm_used[scene_id] = self._get_scene_queries_used(scene_id)

            return RateLimitState(
                global_tpm_used=self._get_global_tokens_used(),
                global_qpm_used=self._get_global_queries_used(),
                scene_tpm_used=scene_tpm_used,
                scene_qpm_used=scene_qpm_used,
                window_start=self._window_start,
                window_end=self._window_end,
            )

    def reset(self):
        with self._lock:
            self.global_token_slots = [0] * self.window_size_seconds
            self.global_query_slots = [0] * self.window_size_seconds
            self.scene_token_slots = {}
            self.scene_query_slots = {}
            self.current_slot_index = 0
            self.last_update_time = time.time()


class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self._lock = threading.RLock()
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity * 0.5
        self.last_refill_time = time.time()

    def _refill(self):
        now = time.time()
        seconds_passed = now - self.last_refill_time
        self.tokens = min(
            self.capacity,
            self.tokens + seconds_passed * self.refill_rate
        )
        self.last_refill_time = now

    def try_consume(self, tokens):
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
