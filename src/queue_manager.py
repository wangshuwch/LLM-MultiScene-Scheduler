import threading
from collections import deque
from datetime import datetime
from .models import (
    LLMRequest,
    SceneConfig,
    QueueState,
    QueueStats,
    SceneNotFoundError,
    SceneDisabledError,
    QueueFullError,
    RequestTimeoutError,
)


class SceneQueue:
    def __init__(self, max_size):
        self.queue = deque()
        self.waiting_tokens = 0
        self.max_size = max_size


class QueueManager:
    def __init__(self, scene_configs):
        self._lock = threading.RLock()
        self._scene_queues = {}
        self._scene_configs = {}
        self._stats = QueueStats()

        for cfg in scene_configs:
            self._scene_configs[cfg.scene_id] = cfg
            self._scene_queues[cfg.scene_id] = SceneQueue(cfg.queue_size)

    def enqueue(self, scene_id, req):
        with self._lock:
            if scene_id not in self._scene_queues:
                raise SceneNotFoundError("Scene " + scene_id + " not found")

            cfg = self._scene_configs.get(scene_id)
            if not cfg or not cfg.is_enabled:
                raise SceneDisabledError("Scene " + scene_id + " is disabled")

            sq = self._scene_queues[scene_id]
            if len(sq.queue) >= sq.max_size:
                self._stats.total_rejected += 1
                raise QueueFullError("Queue for scene " + scene_id + " is full")

            req.enqueue_time = datetime.now()
            sq.queue.append(req)
            sq.waiting_tokens += req.token_estimate
            self._stats.total_enqueued += 1

    def dequeue(self):
        with self._lock:
            best_scene = None
            best_priority = float("inf")
            best_enqueue_time = None

            for scene_id, sq in self._scene_queues.items():
                if not sq.queue:
                    continue

                cfg = self._scene_configs[scene_id]
                front_req = sq.queue[0]

                if cfg.priority < best_priority:
                    best_priority = cfg.priority
                    best_scene = scene_id
                    best_enqueue_time = front_req.enqueue_time
                elif cfg.priority == best_priority:
                    if best_enqueue_time is None or front_req.enqueue_time < best_enqueue_time:
                        best_scene = scene_id
                        best_enqueue_time = front_req.enqueue_time

            if best_scene is None:
                return None

            sq = self._scene_queues[best_scene]
            req = sq.queue.popleft()
            sq.waiting_tokens -= req.token_estimate
            self._stats.total_dequeued += 1
            return req

    def queue_length(self, scene_id):
        with self._lock:
            sq = self._scene_queues.get(scene_id)
            return len(sq.queue) if sq else 0

    def total_queue_length(self):
        with self._lock:
            return sum(len(sq.queue) for sq in self._scene_queues.values())

    def cleanup_expired(self):
        with self._lock:
            cleaned = 0
            now = datetime.now()

            for scene_id, sq in self._scene_queues.items():
                new_queue = deque()
                new_waiting_tokens = 0

                for req in sq.queue:
                    if now > req.deadline:
                        self._stats.total_timed_out += 1
                        cleaned += 1
                        if req.callback:
                            req.callback(None, RequestTimeoutError())
                    else:
                        new_queue.append(req)
                        new_waiting_tokens += req.token_estimate

                sq.queue = new_queue
                sq.waiting_tokens = new_waiting_tokens

            return cleaned

    def get_queue_states(self):
        with self._lock:
            states = []
            for scene_id, sq in self._scene_queues.items():
                state = QueueState(
                    scene_id=scene_id,
                    queue_length=len(sq.queue),
                    waiting_tokens=sq.waiting_tokens,
                )
                if sq.queue:
                    state.oldest_enqueue_time = sq.queue[0].enqueue_time
                states.append(state)
            return states

    def get_stats(self):
        with self._lock:
            return QueueStats(
                total_enqueued=self._stats.total_enqueued,
                total_dequeued=self._stats.total_dequeued,
                total_rejected=self._stats.total_rejected,
                total_timed_out=self._stats.total_timed_out,
            )
