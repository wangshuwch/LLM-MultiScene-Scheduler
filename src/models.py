from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Callable, Any
from datetime import datetime, timedelta
import uuid


class RequestState(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class GlobalConfig:
    total_concurrent_tokens: int
    global_tpm: int
    global_qpm: int
    window_size_seconds: int = 60
    window_step_seconds: int = 1
    worker_count: int = 10
    max_concurrent_requests: int = 100


@dataclass
class SceneConfig:
    scene_id: str
    name: str
    priority: int
    max_concurrent_tokens: int
    weight: float = 1.0
    scene_tpm: int = 0
    scene_qpm: int = 0
    is_enabled: bool = True
    queue_size: int = 1000
    timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    max_concurrent_requests: int = 50


@dataclass
class SceneState:
    scene_id: str
    config: SceneConfig
    current_usage: int = 0
    queue_length: int = 0
    waiting_tokens: int = 0
    active_requests: int = 0


@dataclass
class LLMRequest:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scene_id: str = ""
    prompt: str = ""
    max_output_token: int = 0
    token_estimate: int = 0
    enqueue_time: Optional[datetime] = None
    deadline: Optional[datetime] = None
    callback: Optional[Callable[["LLMResponse", Optional[Exception]], Any]] = None


@dataclass
class LLMResponse:
    request_id: str = ""
    scene_id: str = ""
    content: str = ""
    tokens_used: int = 0
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))


@dataclass
class ResourceState:
    total_concurrent_tokens: int
    used_concurrent_tokens: int = 0
    available_concurrent_tokens: int = 0
    max_concurrent_requests: int = 0
    used_concurrent_requests: int = 0
    scene_concurrent_usage: Dict[str, int] = field(default_factory=dict)
    scene_concurrent_requests: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.available_concurrent_tokens = self.total_concurrent_tokens - self.used_concurrent_tokens


@dataclass
class RateLimitState:
    global_tpm_used: int = 0
    global_qpm_used: int = 0
    scene_tpm_used: Dict[str, int] = field(default_factory=dict)
    scene_qpm_used: Dict[str, int] = field(default_factory=dict)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


@dataclass
class QueueState:
    scene_id: str
    queue_length: int = 0
    waiting_tokens: int = 0
    oldest_enqueue_time: Optional[datetime] = None


@dataclass
class QueueStats:
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_rejected: int = 0
    total_timed_out: int = 0
    average_wait_time: timedelta = field(default_factory=lambda: timedelta(seconds=0))


class SchedulerError(Exception):
    pass


class SceneNotFoundError(SchedulerError):
    pass


class SceneDisabledError(SchedulerError):
    pass


class QueueFullError(SchedulerError):
    pass


class RequestTimeoutError(SchedulerError):
    pass


class SchedulerStoppedError(SchedulerError):
    pass


class RateLimitError(SchedulerError):
    pass


class ResourceExhaustedError(SchedulerError):
    pass


class InvalidRequestError(SchedulerError):
    pass
