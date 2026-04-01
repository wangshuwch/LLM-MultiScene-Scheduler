import threading
import time
import uuid
from typing import Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .models import (
    LLMResponse,
    SceneNotFoundError,
    SceneDisabledError,
    SchedulerStoppedError,
    RequestTimeoutError,
    RateLimitError,
)
from .resource_manager import ResourceManager
from .rate_limiter import SlidingWindowRateLimiter
from .queue_manager import QueueManager
from .token_estimator import SimpleEstimator
from .metrics import MetricsCollector
from .state_analyzer import (
    SystemStateAnalyzer,
    SchedulingStrategyConfig,
    SystemState,
)


class LLMClient:
    def call(self, prompt, max_output_token):
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def __init__(self, delay=0.1):
        self.delay = delay

    def call(self, prompt, max_output_token):
        if self.delay > 0:
            time.sleep(self.delay)
        return LLMResponse(
            content="Mock response for: " + prompt[:min(20, len(prompt))],
            tokens_used=len(prompt) // 4 + max_output_token,
        )


class SchedulerConfig:
    def __init__(
        self,
        global_config,
        scene_configs,
        cleanup_interval=30.0,
        dispatch_interval=0.01,
        global_queue_size=10000,
    ):
        self.global_config = global_config
        self.scene_configs = scene_configs
        self.cleanup_interval = cleanup_interval
        self.dispatch_interval = dispatch_interval
        self.global_queue_size = global_queue_size


class Scheduler:
    def __init__(
        self,
        config,
        llm_client=None,
        token_estimator=None,
        metrics_collector=None,
        scheduling_strategy_config=None,
    ):
        self._config = config
        self._llm_client = llm_client or MockLLMClient()
        self._token_estimator = token_estimator or SimpleEstimator()
        self._metrics = metrics_collector or MetricsCollector()

        self._resource_manager = ResourceManager(
            total_capacity=config.global_config.total_concurrent_tokens,
            max_concurrent_requests=config.global_config.max_concurrent_requests
        )
        self._rate_limiter = SlidingWindowRateLimiter(
            global_tpm=config.global_config.global_tpm,
            global_qpm=config.global_config.global_qpm,
            window_size_seconds=config.global_config.window_size_seconds,
            window_step_seconds=config.global_config.window_step_seconds,
        )
        self._queue_manager = QueueManager(config.scene_configs, global_queue_size=config.global_queue_size)
        self._state_analyzer = SystemStateAnalyzer(scheduling_strategy_config)
        self._last_system_state: Optional[SystemState] = None

        self._scene_configs = {}
        for cfg in config.scene_configs:
            self._scene_configs[cfg.scene_id] = cfg
            self._resource_manager.set_scene_config(cfg)
            self._rate_limiter.set_scene_config(cfg)

        self._dispatch_event = threading.Event()

        self._metrics.set_total_concurrent_tokens(config.global_config.total_concurrent_tokens)

        self._running = False
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self._executor = None
        self._threads = []

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._executor = ThreadPoolExecutor(max_workers=self._config.global_config.worker_count)

            self._threads = [
                threading.Thread(target=self._dispatch_loop, daemon=True),
                threading.Thread(target=self._cleanup_loop, daemon=True),
                threading.Thread(target=self._metrics_loop, daemon=True),
            ]
            for t in self._threads:
                t.start()

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

            for t in self._threads:
                t.join(timeout=5.0)

            if self._executor:
                self._executor.shutdown(wait=True, cancel_futures=False)

    def submit(self, req):
        if not self._running:
            raise SchedulerStoppedError()

        if not req.request_id:
            req.request_id = str(uuid.uuid4())

        if req.token_estimate <= 0:
            req.token_estimate = self._token_estimator.estimate(
                req.prompt, req.max_output_token
            )

        cfg = self._scene_configs.get(req.scene_id)
        if not cfg:
            raise SceneNotFoundError("Scene " + req.scene_id + " not found")
        if not cfg.is_enabled:
            raise SceneDisabledError("Scene " + req.scene_id + " is disabled")

        req.deadline = datetime.now() + cfg.timeout

        result_event = threading.Event()
        result = {"response": None, "error": None}

        def callback(resp, err):
            result["response"] = resp
            result["error"] = err
            result_event.set()

        req.callback = callback
        self.submit_async(req, callback)

        result_event.wait()

        if result["error"]:
            raise result["error"]
        return result["response"]

    def submit_async(self, req, callback):
        if not self._running:
            raise SchedulerStoppedError()

        if not req.request_id:
            req.request_id = str(uuid.uuid4())

        if req.token_estimate <= 0:
            req.token_estimate = self._token_estimator.estimate(
                req.prompt, req.max_output_token
            )

        req.callback = callback

        cfg = self._scene_configs.get(req.scene_id)
        if not cfg:
            raise SceneNotFoundError("Scene " + req.scene_id + " not found")

        req.deadline = datetime.now() + cfg.timeout

        self._metrics.inc_requests_total(req.scene_id)

        if not self._rate_limiter.try_acquire(req.scene_id, req.token_estimate):
            self._metrics.inc_requests_rate_limited(req.scene_id)
            raise RateLimitError("Rate limit exceeded for scene " + req.scene_id)

        self._queue_manager.enqueue(req.scene_id, req)

    def get_resource_state(self):
        return self._resource_manager.get_state()

    def get_queue_states(self):
        return self._queue_manager.get_queue_states()

    def get_rate_limit_state(self):
        return self._rate_limiter.get_rate_limit_state()

    def update_scene_config(self, config):
        with self._lock:
            self._scene_configs[config.scene_id] = config
            self._resource_manager.set_scene_config(config)
            self._rate_limiter.set_scene_config(config)

    def update_scheduling_strategy_config(self, config: SchedulingStrategyConfig) -> None:
        with self._lock:
            self._state_analyzer.update_config(config)

    def get_last_system_state(self) -> Optional[SystemState]:
        with self._lock:
            return self._last_system_state

    def _dispatch_loop(self):
        while not self._stop_event.is_set():
            self._try_dispatch()
            self._dispatch_event.wait(timeout=self._config.dispatch_interval)
            self._dispatch_event.clear()

    def _try_dispatch(self):
        candidates = self._queue_manager.get_candidates(max_per_scene=10)
        if not candidates:
            return

        resource_state = self._resource_manager.get_state()
        queue_states = self._queue_manager.get_queue_states()
        rate_limit_state = self._rate_limiter.get_rate_limit_state()

        system_state = self._state_analyzer.analyze(
            resource_state=resource_state,
            queue_states=queue_states,
            rate_limit_state=rate_limit_state,
            scene_configs=self._scene_configs,
            global_tpm_limit=self._config.global_config.global_tpm,
            global_qpm_limit=self._config.global_config.global_qpm,
        )
        self._last_system_state = system_state

        def calculate_effective_priority(candidate):
            wait_seconds = (datetime.now() - candidate.enqueue_time).total_seconds()
            aging_bonus = wait_seconds // 30
            return (candidate.priority - aging_bonus, candidate.enqueue_time)

        candidates.sort(key=calculate_effective_priority)
        total_waiting_tokens = self._queue_manager.get_total_waiting_tokens()

        dispatched = set()
        for candidate in candidates:
            if candidate.request.request_id in dispatched:
                continue

            if datetime.now() > candidate.request.deadline:
                req = self._queue_manager.dequeue_specific_request(candidate.scene_id, candidate.request.request_id)
                if req:
                    self._metrics.inc_requests_timeout(req.scene_id)
                    if req.callback:
                        req.callback(None, RequestTimeoutError())
                continue

            scene_health = system_state.scene_healths.get(candidate.scene_id)
            if scene_health:
                if self._state_analyzer.is_scene_rate_limited_soon(scene_health, candidate.request.token_estimate):
                    continue

            if not self._rate_limiter.try_acquire(candidate.scene_id, candidate.request.token_estimate):
                continue

            if self._resource_manager.can_acquire(candidate.scene_id, candidate.request.token_estimate, total_waiting_tokens):
                req = self._queue_manager.dequeue_specific_request(candidate.scene_id, candidate.request.request_id)
                if req and self._resource_manager.try_acquire(req.scene_id, req.token_estimate, total_waiting_tokens):
                    if self._executor:
                        self._executor.submit(self._execute_request, req)
                    dispatched.add(req.request_id)
                    return

    def _execute_request(self, req):
        start_time = datetime.now()
        queue_time = (start_time - req.enqueue_time).total_seconds() if req.enqueue_time else 0
        self._metrics.observe_queue_time(req.scene_id, queue_time)

        try:
            resp = self._llm_client.call(req.prompt, req.max_output_token)
            resp.request_id = req.request_id
            resp.scene_id = req.scene_id
            resp.duration = datetime.now() - start_time

            self._metrics.inc_requests_success(req.scene_id)
            self._metrics.observe_execution_time(req.scene_id, resp.duration.total_seconds())
            if req.callback:
                req.callback(resp, None)
        except Exception as e:
            self._metrics.inc_requests_failed(req.scene_id)
            if req.callback:
                req.callback(None, e)
        finally:
            self._resource_manager.release(req.scene_id, req.token_estimate)
            self._dispatch_event.set()

    def _cleanup_loop(self):
        while not self._stop_event.is_set():
            self._queue_manager.cleanup_expired()
            time.sleep(self._config.cleanup_interval)

    def _metrics_loop(self):
        while not self._stop_event.is_set():
            self._update_metrics()
            time.sleep(1.0)

    def _update_metrics(self):
        resource_state = self._resource_manager.get_state()
        self._metrics.set_used_concurrent_tokens(resource_state.used_concurrent_tokens)
        self._metrics.set_available_concurrent_tokens(resource_state.available_concurrent_tokens)

        for scene_id, usage in resource_state.scene_concurrent_usage.items():
            self._metrics.set_scene_concurrent_usage(scene_id, usage)

        rate_limit_state = self._rate_limiter.get_rate_limit_state()
        self._metrics.set_global_tpm_used(rate_limit_state.global_tpm_used)
        self._metrics.set_global_qpm_used(rate_limit_state.global_qpm_used)

        for scene_id, tpm_used in rate_limit_state.scene_tpm_used.items():
            self._metrics.set_scene_tpm_used(scene_id, tpm_used)

        for scene_id, qpm_used in rate_limit_state.scene_qpm_used.items():
            self._metrics.set_scene_qpm_used(scene_id, qpm_used)

        queue_states = self._queue_manager.get_queue_states()
        for qs in queue_states:
            self._metrics.set_queue_length(qs.scene_id, qs.queue_length)
            self._metrics.set_queue_waiting_tokens(qs.scene_id, qs.waiting_tokens)
