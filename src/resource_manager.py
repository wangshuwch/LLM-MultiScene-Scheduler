import threading
from typing import Dict, Optional
from .models import ResourceState, SceneConfig


class ResourceManager:
    def __init__(self, total_capacity: int):
        self._lock = threading.RLock()
        self._total_capacity = total_capacity
        self._used_tokens = 0
        self._scene_usage = {}
        self._scene_max_tokens = {}
        self._scene_configs = {}

    def set_scene_config(self, config: SceneConfig) -> None:
        with self._lock:
            self._scene_configs[config.scene_id] = config
            self._scene_max_tokens[config.scene_id] = config.max_concurrent_tokens

    def set_scene_max_tokens(self, scene_id: str, max_tokens: int) -> None:
        with self._lock:
            self._scene_max_tokens[scene_id] = max_tokens

    def _calculate_total_demand(self, queue_waiting_tokens: int = 0) -> int:
        return self._used_tokens + queue_waiting_tokens

    def _is_resource_abundant(self, queue_waiting_tokens: int = 0) -> bool:
        total_demand = self._calculate_total_demand(queue_waiting_tokens)
        return total_demand <= self._total_capacity

    def _check_can_acquire(self, scene_id: str, tokens: int, queue_waiting_tokens: int = 0) -> bool:
        available = self._total_capacity - self._used_tokens
        if tokens > available:
            return False

        if not self._is_resource_abundant(queue_waiting_tokens):
            if scene_id in self._scene_max_tokens:
                max_tokens = self._scene_max_tokens[scene_id]
                current_usage = self._scene_usage.get(scene_id, 0)
                if current_usage + tokens > max_tokens:
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
            self._scene_usage[scene_id] = self._scene_usage.get(scene_id, 0) + tokens
            return True

    def release(self, scene_id: str, tokens: int) -> None:
        with self._lock:
            if self._used_tokens >= tokens:
                self._used_tokens -= tokens
            else:
                self._used_tokens = 0

            if scene_id in self._scene_usage:
                if self._scene_usage[scene_id] >= tokens:
                    self._scene_usage[scene_id] -= tokens
                    if self._scene_usage[scene_id] == 0:
                        del self._scene_usage[scene_id]
                else:
                    del self._scene_usage[scene_id]

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
                scene_concurrent_usage=self._scene_usage.copy()
            )
            state.available_concurrent_tokens = state.total_concurrent_tokens - state.used_concurrent_tokens
            return state
