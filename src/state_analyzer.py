from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List
from .models import ResourceState, QueueState, RateLimitState, SceneConfig


class LoadLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BottleneckResource(Enum):
    CONCURRENT_TOKENS = "concurrent_tokens"
    TPM = "tpm"
    QPM = "qpm"
    NONE = "none"


@dataclass
class SceneHealth:
    scene_id: str
    queue_length: int = 0
    waiting_tokens: int = 0
    tpm_used: int = 0
    tpm_limit: int = 0
    qpm_used: int = 0
    qpm_limit: int = 0
    concurrent_usage: int = 0
    concurrent_limit: int = 0


@dataclass
class SystemState:
    load_level: LoadLevel = LoadLevel.LOW
    bottleneck_resource: BottleneckResource = BottleneckResource.NONE
    resource_utilization: float = 0.0
    tpm_utilization: float = 0.0
    qpm_utilization: float = 0.0
    total_queue_length: int = 0
    total_waiting_tokens: int = 0
    scene_healths: Dict[str, SceneHealth] = field(default_factory=dict)


@dataclass
class SchedulingStrategyConfig:
    low_load_threshold: float = 0.5
    medium_load_threshold: float = 0.8
    tpm_warning_threshold: float = 0.9
    qpm_warning_threshold: float = 0.9


class SystemStateAnalyzer:
    def __init__(self, config: Optional[SchedulingStrategyConfig] = None):
        self._config = config or SchedulingStrategyConfig()

    def analyze(
        self,
        resource_state: ResourceState,
        queue_states: List[QueueState],
        rate_limit_state: RateLimitState,
        scene_configs: Dict[str, SceneConfig],
        global_tpm_limit: int,
        global_qpm_limit: int,
    ) -> SystemState:
        state = SystemState()

        resource_util = 0.0
        if resource_state.total_concurrent_tokens > 0:
            resource_util = resource_state.used_concurrent_tokens / resource_state.total_concurrent_tokens
        state.resource_utilization = resource_util

        tpm_util = 0.0
        if global_tpm_limit > 0:
            tpm_util = rate_limit_state.global_tpm_used / global_tpm_limit
        state.tpm_utilization = tpm_util

        qpm_util = 0.0
        if global_qpm_limit > 0:
            qpm_util = rate_limit_state.global_qpm_used / global_qpm_limit
        state.qpm_utilization = qpm_util

        state.load_level = self._determine_load_level(resource_util, tpm_util, qpm_util)
        state.bottleneck_resource = self._identify_bottleneck(resource_util, tpm_util, qpm_util)

        total_queue_length = 0
        total_waiting_tokens = 0
        for qs in queue_states:
            total_queue_length += qs.queue_length
            total_waiting_tokens += qs.waiting_tokens
        state.total_queue_length = total_queue_length
        state.total_waiting_tokens = total_waiting_tokens

        for scene_id, cfg in scene_configs.items():
            health = SceneHealth(scene_id=scene_id)
            health.concurrent_usage = resource_state.scene_concurrent_usage.get(scene_id, 0)
            health.concurrent_limit = cfg.max_concurrent_tokens
            health.tpm_used = rate_limit_state.scene_tpm_used.get(scene_id, 0)
            health.tpm_limit = cfg.scene_tpm
            health.qpm_used = rate_limit_state.scene_qpm_used.get(scene_id, 0)
            health.qpm_limit = cfg.scene_qpm

            for qs in queue_states:
                if qs.scene_id == scene_id:
                    health.queue_length = qs.queue_length
                    health.waiting_tokens = qs.waiting_tokens
                    break

            state.scene_healths[scene_id] = health

        return state

    def _determine_load_level(
        self,
        resource_util: float,
        tpm_util: float,
        qpm_util: float,
    ) -> LoadLevel:
        max_util = max(resource_util, tpm_util, qpm_util)
        if max_util < self._config.low_load_threshold:
            return LoadLevel.LOW
        elif max_util < self._config.medium_load_threshold:
            return LoadLevel.MEDIUM
        else:
            return LoadLevel.HIGH

    def _identify_bottleneck(
        self,
        resource_util: float,
        tpm_util: float,
        qpm_util: float,
    ) -> BottleneckResource:
        max_util = max(resource_util, tpm_util, qpm_util)
        if max_util < 0.5:
            return BottleneckResource.NONE
        if max_util == resource_util:
            return BottleneckResource.CONCURRENT_TOKENS
        elif max_util == tpm_util:
            return BottleneckResource.TPM
        else:
            return BottleneckResource.QPM

    def is_scene_rate_limited_soon(
        self,
        scene_health: SceneHealth,
        request_tokens: int,
    ) -> bool:
        if scene_health.tpm_limit > 0:
            tpm_after = scene_health.tpm_used + request_tokens
            if tpm_after > scene_health.tpm_limit * self._config.tpm_warning_threshold:
                return True
        if scene_health.qpm_limit > 0:
            qpm_after = scene_health.qpm_used + 1
            if qpm_after > scene_health.qpm_limit * self._config.qpm_warning_threshold:
                return True
        return False

    def update_config(self, config: SchedulingStrategyConfig) -> None:
        self._config = config
