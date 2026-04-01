import threading
from typing import Dict, Optional
from .models import ResourceState, SceneConfig


class ResourceManager:
    def __init__(self, total_capacity: int, max_concurrent_requests: int = 100):
        self._lock = threading.RLock()
        self._total_capacity = total_capacity
        self._max_concurrent_requests = max_concurrent_requests
        self._used_tokens = 0
        self._used_concurrent_requests = 0
        self._scene_usage = {}
        self._scene_concurrent_requests = {}
        self._scene_max_tokens = {}
        self._scene_max_requests = {}
        self._scene_configs = {}

    def set_scene_config(self, config: SceneConfig) -> None:
        with self._lock:
            self._scene_configs[config.scene_id] = config
            self._scene_max_tokens[config.scene_id] = config.max_concurrent_tokens
            self._scene_max_requests[config.scene_id] = config.max_concurrent_requests

    def set_scene_max_tokens(self, scene_id: str, max_tokens: int) -> None:
        with self._lock:
            self._scene_max_tokens[scene_id] = max_tokens

    def set_scene_max_requests(self, scene_id: str, max_requests: int) -> None:
        with self._lock:
            self._scene_max_requests[scene_id] = max_requests

    def _calculate_total_demand(self, queue_waiting_tokens: int = 0) -> int:
        return self._used_tokens + queue_waiting_tokens

    def _is_resource_abundant(self, queue_waiting_tokens: int = 0) -> bool:
        total_demand = self._calculate_total_demand(queue_waiting_tokens)
        return total_demand <= self._total_capacity

    def _check_can_acquire(self, scene_id: str, tokens: int, queue_waiting_tokens: int = 0) -> bool:
        available = self._total_capacity - self._used_tokens
        if tokens > available:
            return False

        if self._used_concurrent_requests >= self._max_concurrent_requests:
            return False

        if scene_id in self._scene_max_tokens:
            max_tokens = self._scene_max_tokens[scene_id]
            current_usage = self._scene_usage.get(scene_id, 0)
            if current_usage + tokens > max_tokens:
                return False

        if scene_id in self._scene_max_requests:
            max_requests = self._scene_max_requests[scene_id]
            current_requests = self._scene_concurrent_requests.get(scene_id, 0)
            if current_requests + 1 > max_requests:
                return False

        return True

    def can_acquire(self, scene_id: str, tokens: int, queue_waiting_tokens: int = 0) -> bool:
        with self._lock:
            return self._check_can_acquire(scene_id, tokens, queue_waiting_tokens)

    def try_acquire(self, scene_id: str, tokens: int, queue_waiting_tokens: int = 0) -> bool:
        with self._lock:
            if not self._check_can_acquire(scene_id, tokens, queue_waiting_tokens):
                return False

            self._used_tokens += tokens
            self._used_concurrent_requests += 1
            self._scene_usage[scene_id] = self._scene_usage.get(scene_id, 0) + tokens
            self._scene_concurrent_requests[scene_id] = self._scene_concurrent_requests.get(scene_id, 0) + 1
            return True

    def release(self, scene_id: str, tokens: int) -> None:
        with self._lock:
            if self._used_tokens >= tokens:
                self._used_tokens -= tokens
            else:
                self._used_tokens = 0

            if self._used_concurrent_requests > 0:
                self._used_concurrent_requests -= 1
            else:
                self._used_concurrent_requests = 0

            if scene_id in self._scene_usage:
                if self._scene_usage[scene_id] >= tokens:
                    self._scene_usage[scene_id] -= tokens
                    if self._scene_usage[scene_id] == 0:
                        del self._scene_usage[scene_id]
                else:
                    del self._scene_usage[scene_id]

            if scene_id in self._scene_concurrent_requests:
                if self._scene_concurrent_requests[scene_id] > 0:
                    self._scene_concurrent_requests[scene_id] -= 1
                    if self._scene_concurrent_requests[scene_id] == 0:
                        del self._scene_concurrent_requests[scene_id]
                else:
                    del self._scene_concurrent_requests[scene_id]

    def get_usage(self, scene_id: str) -> int:
        with self._lock:
            return self._scene_usage.get(scene_id, 0)

    def get_total_capacity(self) -> int:
        return self._total_capacity

    def get_state(self) -> ResourceState:
        with self._lock:
            state = ResourceState(
                total_concurrent_tokens=self._total_capacity,
                used_concurrent_tokens=self._used_tokens,
                max_concurrent_requests=self._max_concurrent_requests,
                used_concurrent_requests=self._used_concurrent_requests,
                scene_concurrent_usage=self._scene_usage.copy(),
                scene_concurrent_requests=self._scene_concurrent_requests.copy()
            )
            state.available_concurrent_tokens = state.total_concurrent_tokens - state.used_concurrent_tokens
            return state
