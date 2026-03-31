import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
import time
from datetime import timedelta

from src.models import (
    SceneConfig,
    LLMRequest,
    GlobalConfig,
    SceneNotFoundError,
    QueueFullError,
)
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.global_config = GlobalConfig(
            total_concurrent_tokens=2000,
            global_tpm=10000,
            global_qpm=100,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=2,
        )

        self.scene_configs = [
            SceneConfig(
                scene_id="test_scene_1",
                name="Test Scene 1",
                priority=1,
                max_concurrent_tokens=1000,
                weight=1.0,
                timeout=timedelta(seconds=30),
            ),
            SceneConfig(
                scene_id="test_scene_2",
                name="Test Scene 2",
                priority=2,
                max_concurrent_tokens=1000,
                weight=1.0,
                timeout=timedelta(seconds=30),
            ),
        ]

        self.scheduler_config = SchedulerConfig(
            global_config=self.global_config,
            scene_configs=self.scene_configs,
        )

        self.scheduler = Scheduler(
            config=self.scheduler_config,
            llm_client=MockLLMClient(delay=0.05),
            token_estimator=SimpleEstimator(),
        )

    def tearDown(self):
        if self.scheduler:
            self.scheduler.stop()

    def test_submit_sync_request(self):
        self.scheduler.start()
        time.sleep(0.1)

        req = LLMRequest(
            scene_id="test_scene_1",
            prompt="Hello, test!",
            max_output_token=50,
        )

        resp = self.scheduler.submit(req)
        self.assertIsNotNone(resp)
        self.assertIn("Mock response", resp.content)

    def test_submit_async_request(self):
        self.scheduler.start()
        time.sleep(0.1)

        result = {"done": False, "error": None}

        def callback(resp, err):
            result["done"] = True
            result["error"] = err
            result["resp"] = resp

        req = LLMRequest(
            scene_id="test_scene_1",
            prompt="Hello, async test!",
            max_output_token=50,
        )

        self.scheduler.submit_async(req, callback)

        timeout = 2.0
        start = time.time()
        while not result["done"] and time.time() - start < timeout:
            time.sleep(0.05)

        self.assertTrue(result["done"])
        self.assertIsNone(result["error"])

    def test_scene_not_found(self):
        self.scheduler.start()
        time.sleep(0.1)

        req = LLMRequest(
            scene_id="nonexistent_scene",
            prompt="Test",
            max_output_token=50,
        )

        with self.assertRaises(SceneNotFoundError):
            self.scheduler.submit(req)

    def test_resource_state(self):
        self.scheduler.start()
        time.sleep(0.1)

        state = self.scheduler.get_resource_state()
        self.assertEqual(state.total_concurrent_tokens, 2000)
        self.assertEqual(state.used_concurrent_tokens, 0)
        self.assertEqual(state.available_concurrent_tokens, 2000)

    def test_queue_states(self):
        self.scheduler.start()
        time.sleep(0.1)

        states = self.scheduler.get_queue_states()
        self.assertEqual(len(states), 2)

    def test_rate_limit_state(self):
        self.scheduler.start()
        time.sleep(0.1)

        state = self.scheduler.get_rate_limit_state()
        self.assertEqual(state.global_tpm_used, 0)
        self.assertEqual(state.global_qpm_used, 0)


if __name__ == "__main__":
    unittest.main()
