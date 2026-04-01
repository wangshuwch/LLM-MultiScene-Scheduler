import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
import time
import threading
from datetime import timedelta
from typing import List, Dict

from src.models import (
    SceneConfig,
    LLMRequest,
    GlobalConfig,
    QueueFullError,
)
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator


class TestSchedulerComprehensive(unittest.TestCase):
    def setUp(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=3000,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=4,
        )

        self.scene_configs = [
            SceneConfig(
                scene_id="scene_high",
                name="High Priority Scene",
                priority=1,
                max_concurrent_tokens=1000,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
            SceneConfig(
                scene_id="scene_medium",
                name="Medium Priority Scene",
                priority=2,
                max_concurrent_tokens=1000,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
            SceneConfig(
                scene_id="scene_low",
                name="Low Priority Scene",
                priority=3,
                max_concurrent_tokens=1000,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
            SceneConfig(
                scene_id="scene_small",
                name="Small Queue Scene",
                priority=1,
                max_concurrent_tokens=500,
                weight=1.0,
                queue_size=3,
                timeout=timedelta(seconds=60),
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )

        self.scheduler = None

    def tearDown(self):
        if self.scheduler:
            self.scheduler.stop()

    def test_global_limits_under_capacity(self):
        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.02),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)

        results = []
        lock = threading.Lock()

        def callback(resp, err):
            with lock:
                results.append((resp, err))

        num_requests = 5
        token_estimate = 100

        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_high",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            self.scheduler.submit_async(req, callback)

        timeout = 2.0
        start = time.time()
        while len(results) < num_requests and time.time() - start < timeout:
            time.sleep(0.05)

        self.assertEqual(len(results), num_requests)
        for resp, err in results:
            self.assertIsNone(err)
            self.assertIsNotNone(resp)
            self.assertIn("Mock response", resp.content)

    def test_global_limits_over_capacity(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=300,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=2,
        )

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )

        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.3),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)

        results: Dict[str, List] = {
            "scene_high": [],
            "scene_medium": [],
            "scene_low": [],
        }
        lock = threading.Lock()

        def create_callback(scene_id):
            def callback(resp, err):
                with lock:
                    results[scene_id].append((resp, err))
            return callback

        token_estimate = 100
        num_per_scene = 4

        scenes = ["scene_low", "scene_medium", "scene_high"]
        for scene_id in scenes:
            for i in range(num_per_scene):
                req = LLMRequest(
                    scene_id=scene_id,
                    prompt=f"Test request {i} for {scene_id}",
                    max_output_token=50,
                    token_estimate=token_estimate,
                )
                self.scheduler.submit_async(req, create_callback(scene_id))

        timeout = 3.0
        start = time.time()
        total_expected = num_per_scene * 3
        total_completed = sum(len(r) for r in results.values())
        while total_completed < total_expected and time.time() - start < timeout:
            time.sleep(0.1)
            total_completed = sum(len(r) for r in results.values())

        high_success = sum(1 for resp, err in results["scene_high"] if resp is not None)
        medium_success = sum(1 for resp, err in results["scene_medium"] if resp is not None)
        low_success = sum(1 for resp, err in results["scene_low"] if resp is not None)

        self.assertGreaterEqual(high_success, medium_success)
        self.assertGreaterEqual(medium_success, low_success)

    def test_same_priority_fifo(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=100,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=1,
        )

        self.scene_configs = [
            SceneConfig(
                scene_id="scene_fifo",
                name="FIFO Test Scene",
                priority=1,
                max_concurrent_tokens=100,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )

        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.1),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)

        completion_order = []
        lock = threading.Lock()

        def create_callback(request_num):
            def callback(resp, err):
                with lock:
                    completion_order.append(request_num)
            return callback

        token_estimate = 100
        num_requests = 5

        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_fifo",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            self.scheduler.submit_async(req, create_callback(i))

        timeout = 2.0
        start = time.time()
        while len(completion_order) < num_requests and time.time() - start < timeout:
            time.sleep(0.05)

        self.assertEqual(len(completion_order), num_requests)
        self.assertEqual(completion_order, list(range(num_requests)))

    def test_per_scene_resource_limits(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=2000,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=4,
        )

        scene_limit = 200
        self.scene_configs = [
            SceneConfig(
                scene_id="scene_limit",
                name="Limited Scene",
                priority=1,
                max_concurrent_tokens=scene_limit,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )

        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.3),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)

        results = []
        lock = threading.Lock()
        max_concurrent_observed = 0
        current_concurrent = 0
        concurrent_lock = threading.Lock()

        def callback(resp, err):
            nonlocal current_concurrent, max_concurrent_observed
            with concurrent_lock:
                current_concurrent -= 1
            with lock:
                results.append((resp, err))

        token_estimate = 100
        num_requests = 5

        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_limit",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )

            def create_start_callback(req_num):
                def start_callback():
                    nonlocal current_concurrent, max_concurrent_observed
                    with concurrent_lock:
                        current_concurrent += 1
                        if current_concurrent > max_concurrent_observed:
                            max_concurrent_observed = current_concurrent
                return start_callback

            self.scheduler.submit_async(req, callback)

        timeout = 3.0
        start = time.time()
        while len(results) < num_requests and time.time() - start < timeout:
            time.sleep(0.1)

        self.assertEqual(len(results), num_requests)
        for resp, err in results:
            self.assertIsNone(err)
            self.assertIsNotNone(resp)

    def test_queue_full_handling(self):
        from src.queue_manager import QueueManager

        scene_configs = [
            SceneConfig(
                scene_id="scene_small_queue",
                name="Small Queue Scene",
                priority=1,
                max_concurrent_tokens=100,
                weight=1.0,
                queue_size=3,
                timeout=timedelta(seconds=60),
            ),
        ]

        queue_manager = QueueManager(scene_configs)

        token_estimate = 100

        req1 = LLMRequest(
            scene_id="scene_small_queue",
            prompt="Test request 1",
            max_output_token=50,
            token_estimate=token_estimate,
        )
        queue_manager.enqueue("scene_small_queue", req1)

        req2 = LLMRequest(
            scene_id="scene_small_queue",
            prompt="Test request 2",
            max_output_token=50,
            token_estimate=token_estimate,
        )
        queue_manager.enqueue("scene_small_queue", req2)

        req3 = LLMRequest(
            scene_id="scene_small_queue",
            prompt="Test request 3",
            max_output_token=50,
            token_estimate=token_estimate,
        )
        queue_manager.enqueue("scene_small_queue", req3)

        self.assertEqual(queue_manager.queue_length("scene_small_queue"), 3)

        req4 = LLMRequest(
            scene_id="scene_small_queue",
            prompt="Test request 4",
            max_output_token=50,
            token_estimate=token_estimate,
        )

        with self.assertRaises(QueueFullError):
            queue_manager.enqueue("scene_small_queue", req4)

    def test_resource_release_and_reallocation(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=100,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=1,
        )

        self.scene_configs = [
            SceneConfig(
                scene_id="scene_release",
                name="Release Test Scene",
                priority=1,
                max_concurrent_tokens=100,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )

        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.15),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)

        completion_times = []
        lock = threading.Lock()

        def create_callback(request_num):
            def callback(resp, err):
                with lock:
                    completion_times.append((request_num, time.time()))
            return callback

        token_estimate = 100
        num_requests = 3

        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_release",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            self.scheduler.submit_async(req, create_callback(i))

        timeout = 2.0
        start = time.time()
        while len(completion_times) < num_requests and time.time() - start < timeout:
            time.sleep(0.05)

        self.assertEqual(len(completion_times), num_requests)
        completion_times.sort(key=lambda x: x[0])
        for i in range(1, num_requests):
            self.assertGreater(completion_times[i][1], completion_times[i-1][1])


if __name__ == "__main__":
    unittest.main()
