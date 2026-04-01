import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
import time
import threading
from datetime import timedelta, datetime

from src.models import (
    SceneConfig,
    LLMRequest,
    GlobalConfig,
    QueueFullError,
)
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator
from src.resource_manager import ResourceManager
from src.queue_manager import QueueManager


class TestFixedFeatures(unittest.TestCase):
    def setUp(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=5000,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=4,
            max_concurrent_requests=20,
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
                max_concurrent_requests=10,
            ),
            SceneConfig(
                scene_id="scene_low",
                name="Low Priority Scene",
                priority=3,
                max_concurrent_tokens=1000,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
            global_queue_size=1000,
        )

        self.scheduler = None

    def tearDown(self):
        if self.scheduler:
            self.scheduler.stop()

    def test_scene_quota_enforced_always(self):
        print("\nTesting scene quota is always enforced...")
        
        self.global_config = GlobalConfig(
            total_concurrent_tokens=10000,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=4,
            max_concurrent_requests=20,
        )
        
        scene_quota = 200
        self.scene_configs = [
            SceneConfig(
                scene_id="scene_quota_test",
                name="Quota Test Scene",
                priority=1,
                max_concurrent_tokens=scene_quota,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
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
        
        def callback(resp, err):
            with lock:
                results.append((resp, err))
        
        token_estimate = 100
        num_requests = 4
        
        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_quota_test",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            self.scheduler.submit_async(req, callback)
        
        timeout = 3.0
        start = time.time()
        
        resource_manager = self.scheduler._resource_manager
        max_scene_usage = 0
        
        while len(results) < num_requests and time.time() - start < timeout:
            time.sleep(0.05)
            state = resource_manager.get_state()
            scene_usage = state.scene_concurrent_usage.get("scene_quota_test", 0)
            if scene_usage > max_scene_usage:
                max_scene_usage = scene_usage
        
        self.assertEqual(len(results), num_requests)
        self.assertLessEqual(max_scene_usage, scene_quota)
        print(f"  ✓ Max scene usage: {max_scene_usage}, Quota: {scene_quota}")

    def test_concurrent_requests_limit(self):
        print("\nTesting concurrent requests limit...")
        
        self.global_config = GlobalConfig(
            total_concurrent_tokens=10000,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=4,
            max_concurrent_requests=3,
        )
        
        self.scene_configs = [
            SceneConfig(
                scene_id="scene_concurrent",
                name="Concurrent Test Scene",
                priority=1,
                max_concurrent_tokens=10000,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
            ),
        ]
        
        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )
        
        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.2),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)
        
        results = []
        lock = threading.Lock()
        current_concurrent = 0
        max_concurrent = 0
        concurrent_lock = threading.Lock()
        
        def callback(resp, err):
            nonlocal current_concurrent
            with concurrent_lock:
                current_concurrent -= 1
            with lock:
                results.append((resp, err))
        
        token_estimate = 100
        num_requests = 6
        
        def track_start():
            nonlocal current_concurrent, max_concurrent
            with concurrent_lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
        
        original_execute = self.scheduler._execute_request
        
        def wrapped_execute(req):
            track_start()
            return original_execute(req)
        
        self.scheduler._execute_request = wrapped_execute
        
        for i in range(num_requests):
            req = LLMRequest(
                scene_id="scene_concurrent",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            self.scheduler.submit_async(req, callback)
        
        timeout = 3.0
        start = time.time()
        while len(results) < num_requests and time.time() - start < timeout:
            time.sleep(0.05)
        
        self.assertEqual(len(results), num_requests)
        self.assertLessEqual(max_concurrent, self.global_config.max_concurrent_requests)
        print(f"  ✓ Max concurrent requests: {max_concurrent}, Limit: {self.global_config.max_concurrent_requests}")

    def test_global_queue_limit(self):
        print("\nTesting global queue limit...")
        
        queue_manager = QueueManager(self.scene_configs, global_queue_size=5)
        
        token_estimate = 100
        
        for i in range(5):
            req = LLMRequest(
                scene_id="scene_high",
                prompt=f"Test request {i}",
                max_output_token=50,
                token_estimate=token_estimate,
            )
            queue_manager.enqueue("scene_high", req)
        
        total_queue = sum(len(sq.queue) for sq in queue_manager._scene_queues.values())
        self.assertEqual(total_queue, 5)
        
        req6 = LLMRequest(
            scene_id="scene_high",
            prompt="Test request 6",
            max_output_token=50,
            token_estimate=token_estimate,
        )
        
        with self.assertRaises(QueueFullError):
            queue_manager.enqueue("scene_high", req6)
        
        print("  ✓ Global queue limit enforced")

    def test_duplicate_request_prevention(self):
        print("\nTesting duplicate request prevention...")
        
        queue_manager = QueueManager(self.scene_configs, global_queue_size=100)
        
        req = LLMRequest(
            scene_id="scene_high",
            prompt="Test request",
            max_output_token=50,
            token_estimate=100,
        )
        
        queue_manager.enqueue("scene_high", req)
        
        with self.assertRaises(QueueFullError):
            queue_manager.enqueue("scene_high", req)
        
        print("  ✓ Duplicate request prevented")

    def test_no_head_blocking(self):
        print("\nTesting no head-of-line blocking...")
        
        self.global_config = GlobalConfig(
            total_concurrent_tokens=200,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=1,
            max_concurrent_requests=10,
        )
        
        self.scene_configs = [
            SceneConfig(
                scene_id="scene_test",
                name="Test Scene",
                priority=1,
                max_concurrent_tokens=200,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
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
        
        results = []
        lock = threading.Lock()
        completed_order = []
        
        def create_callback(req_id):
            def callback(resp, err):
                with lock:
                    completed_order.append(req_id)
                    results.append((resp, err))
            return callback
        
        big_req = LLMRequest(
            scene_id="scene_test",
            prompt="Big request",
            max_output_token=50,
            token_estimate=300,
        )
        self.scheduler.submit_async(big_req, create_callback("big"))
        
        small_req1 = LLMRequest(
            scene_id="scene_test",
            prompt="Small request 1",
            max_output_token=50,
            token_estimate=50,
        )
        self.scheduler.submit_async(small_req1, create_callback("small1"))
        
        small_req2 = LLMRequest(
            scene_id="scene_test",
            prompt="Small request 2",
            max_output_token=50,
            token_estimate=50,
        )
        self.scheduler.submit_async(small_req2, create_callback("small2"))
        
        timeout = 2.0
        start = time.time()
        while len(results) < 3 and time.time() - start < timeout:
            time.sleep(0.05)
        
        self.assertIn("small1", completed_order)
        self.assertIn("small2", completed_order)
        print("  ✓ Small requests can bypass big blocked request")

    def test_aging_mechanism(self):
        print("\nTesting aging mechanism...")
        
        self.global_config = GlobalConfig(
            total_concurrent_tokens=100,
            global_tpm=100000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=1,
            max_concurrent_requests=1,
        )
        
        self.scene_configs = [
            SceneConfig(
                scene_id="scene_high",
                name="High Priority",
                priority=1,
                max_concurrent_tokens=100,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
            ),
            SceneConfig(
                scene_id="scene_low",
                name="Low Priority",
                priority=10,
                max_concurrent_tokens=100,
                weight=1.0,
                queue_size=100,
                timeout=timedelta(seconds=60),
                max_concurrent_requests=10,
            ),
        ]
        
        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
            dispatch_interval=0.005,
        )
        
        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.05),
            token_estimator=SimpleEstimator(),
        )
        self.scheduler.start()
        time.sleep(0.1)
        
        results = []
        lock = threading.Lock()
        low_priority_completed = False
        
        def create_callback(scene):
            def callback(resp, err):
                nonlocal low_priority_completed
                with lock:
                    results.append((scene, resp, err))
                    if scene == "scene_low":
                        low_priority_completed = True
            return callback
        
        low_req = LLMRequest(
            scene_id="scene_low",
            prompt="Low priority request",
            max_output_token=50,
            token_estimate=100,
        )
        low_req.enqueue_time = datetime.now() - timedelta(seconds=100)
        self.scheduler.submit_async(low_req, create_callback("scene_low"))
        
        for i in range(5):
            high_req = LLMRequest(
                scene_id="scene_high",
                prompt=f"High priority request {i}",
                max_output_token=50,
                token_estimate=100,
            )
            self.scheduler.submit_async(high_req, create_callback("scene_high"))
        
        timeout = 3.0
        start = time.time()
        while len(results) < 6 and time.time() - start < timeout:
            time.sleep(0.05)
        
        self.assertTrue(low_priority_completed)
        print("  ✓ Low priority request aged and got scheduled")

    def test_resource_manager_concurrent_requests(self):
        print("\nTesting ResourceManager concurrent requests...")
        
        rm = ResourceManager(total_capacity=1000, max_concurrent_requests=3)
        
        self.assertTrue(rm.can_acquire("scene1", 100))
        self.assertTrue(rm.try_acquire("scene1", 100))
        
        self.assertTrue(rm.can_acquire("scene1", 100))
        self.assertTrue(rm.try_acquire("scene1", 100))
        
        self.assertTrue(rm.can_acquire("scene1", 100))
        self.assertTrue(rm.try_acquire("scene1", 100))
        
        self.assertFalse(rm.can_acquire("scene1", 100))
        self.assertFalse(rm.try_acquire("scene1", 100))
        
        rm.release("scene1", 100)
        self.assertTrue(rm.can_acquire("scene1", 100))
        self.assertTrue(rm.try_acquire("scene1", 100))
        
        state = rm.get_state()
        self.assertEqual(state.used_concurrent_requests, 3)
        print("  ✓ ResourceManager concurrent requests work correctly")


if __name__ == "__main__":
    unittest.main()
