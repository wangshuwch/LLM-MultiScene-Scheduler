import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import threading
from datetime import timedelta
from typing import Optional, Dict, Any
from queue import Queue

from src.models import SceneConfig, LLMRequest, GlobalConfig, LLMResponse
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator
from src.state_analyzer import SchedulingStrategyConfig


class SchedulerService:
    def __init__(
        self,
        use_real_llm: bool = False,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-3.5-turbo",
    ):
        self._response_queue: Queue = Queue()
        self._request_lock = threading.Lock()
        self._request_callbacks: Dict[str, Any] = {}
        self._scheduler: Optional[Scheduler] = None
        self._running = False

        self._init_scheduler(use_real_llm, openai_api_key, openai_model)

    def _init_scheduler(
        self,
        use_real_llm: bool,
        openai_api_key: Optional[str],
        openai_model: str,
    ):
        print("=" * 80)
        print("Initializing LLM Multi-Scene Scheduler Service")
        print("=" * 80)

        global_config = GlobalConfig(
            total_concurrent_tokens=100000,
            global_tpm=1000000,
            global_qpm=10000,
            window_size_seconds=60,
            window_step_seconds=1,
            worker_count=10,
            max_concurrent_requests=100,
        )

        scene_configs = [
            SceneConfig(
                scene_id="chatbot",
                name="Customer Chatbot",
                priority=1,
                max_concurrent_tokens=60000,
                weight=0.5,
                scene_tpm=500000,
                scene_qpm=5000,
                is_enabled=True,
                queue_size=1000,
                timeout=timedelta(minutes=2),
                max_concurrent_requests=60,
            ),
            SceneConfig(
                scene_id="analytics",
                name="Data Analytics",
                priority=2,
                max_concurrent_tokens=50000,
                weight=0.3,
                scene_tpm=300000,
                scene_qpm=3000,
                is_enabled=True,
                queue_size=500,
                timeout=timedelta(minutes=5),
                max_concurrent_requests=30,
            ),
            SceneConfig(
                scene_id="background",
                name="Background Jobs",
                priority=3,
                max_concurrent_tokens=40000,
                weight=0.2,
                scene_tpm=200000,
                scene_qpm=2000,
                is_enabled=True,
                queue_size=200,
                timeout=timedelta(minutes=10),
                max_concurrent_requests=20,
            ),
        ]

        scheduler_config = SchedulerConfig(
            global_config=global_config,
            scene_configs=scene_configs,
            cleanup_interval=30.0,
            dispatch_interval=0.01,
            global_queue_size=5000,
        )

        strategy_config = SchedulingStrategyConfig(
            low_load_threshold=0.5,
            medium_load_threshold=0.8,
            tpm_warning_threshold=0.9,
            qpm_warning_threshold=0.9,
        )

        if use_real_llm:
            from src.clients import OpenAIClient
            llm_client = OpenAIClient(
                api_key=openai_api_key,
                model=openai_model,
                temperature=0.7,
                timeout=60.0,
            )
            print(f"\n✓ Using real LLM: {openai_model}")
        else:
            llm_client = MockLLMClient(delay=0.1)
            print("\n✓ Using mock LLM (for testing)")

        self._scheduler = Scheduler(
            config=scheduler_config,
            llm_client=llm_client,
            token_estimator=SimpleEstimator(),
            scheduling_strategy_config=strategy_config,
        )

    def start(self):
        if self._running:
            return

        print("\nStarting scheduler service...")
        self._scheduler.start()
        self._running = True
        print("✓ Scheduler service started")

    def stop(self):
        if not self._running:
            return

        print("\nStopping scheduler service...")
        self._scheduler.stop()
        self._running = False
        print("✓ Scheduler service stopped")

    def submit(
        self,
        scene_id: str,
        prompt: str,
        max_output_token: int = 100,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        if not self._running:
            raise RuntimeError("Scheduler service is not running")

        req = LLMRequest(
            scene_id=scene_id,
            prompt=prompt,
            max_output_token=max_output_token,
        )

        return self._scheduler.submit(req)

    def submit_async(
        self,
        scene_id: str,
        prompt: str,
        max_output_token: int = 100,
        callback=None,
    ):
        if not self._running:
            raise RuntimeError("Scheduler service is not running")

        req = LLMRequest(
            scene_id=scene_id,
            prompt=prompt,
            max_output_token=max_output_token,
        )

        self._scheduler.submit_async(req, callback)

    def get_stats(self) -> Dict[str, Any]:
        if not self._scheduler:
            return {}

        resource_state = self._scheduler.get_resource_state()
        queue_states = self._scheduler.get_queue_states()
        rate_limit_state = self._scheduler.get_rate_limit_state()
        system_state = self._scheduler.get_last_system_state()

        return {
            "resource": {
                "total_tokens": resource_state.total_concurrent_tokens,
                "used_tokens": resource_state.used_concurrent_tokens,
                "available_tokens": resource_state.available_concurrent_tokens,
                "used_concurrent_requests": resource_state.used_concurrent_requests,
                "scene_usage": resource_state.scene_concurrent_usage,
            },
            "queues": [
                {
                    "scene_id": qs.scene_id,
                    "queue_length": qs.queue_length,
                    "waiting_tokens": qs.waiting_tokens,
                }
                for qs in queue_states
            ],
            "rate_limit": {
                "global_tpm_used": rate_limit_state.global_tpm_used,
                "global_qpm_used": rate_limit_state.global_qpm_used,
                "scene_tpm_used": rate_limit_state.scene_tpm_used,
                "scene_qpm_used": rate_limit_state.scene_qpm_used,
            },
            "system": {
                "load_level": system_state.load_level.value if system_state else None,
                "bottleneck": system_state.bottleneck_resource.value if system_state else None,
                "resource_utilization": system_state.resource_utilization if system_state else None,
            } if system_state else None,
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM Multi-Scene Scheduler Service")
    parser.add_argument(
        "--use-real-llm",
        action="store_true",
        help="Use real OpenAI LLM instead of mock",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key (default: from OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-3.5-turbo",
        help="OpenAI model to use (default: gpt-3.5-turbo)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo after starting service",
    )

    args = parser.parse_args()

    service = SchedulerService(
        use_real_llm=args.use_real_llm,
        openai_api_key=args.api_key,
        openai_model=args.model,
    )

    try:
        service.start()

        if args.demo:
            print("\n" + "=" * 80)
            print("Running Demo...")
            print("=" * 80)

            print("\n1. Submitting chatbot request (sync)...")
            try:
                resp = service.submit(
                    scene_id="chatbot",
                    prompt="Hello, how can I help you today?",
                    max_output_token=100,
                )
                print(f"   ✓ Response: {resp.content[:80]}...")
                print(f"   ✓ Tokens: {resp.tokens_used}")
            except Exception as e:
                print(f"   ✗ Error: {e}")

            print("\n2. Submitting mixed async requests...")
            results = []
            result_lock = threading.Lock()

            def callback(resp, err):
                with result_lock:
                    results.append((resp, err))

            service.submit_async(
                scene_id="chatbot",
                prompt="What's the weather like?",
                max_output_token=100,
                callback=callback,
            )
            service.submit_async(
                scene_id="analytics",
                prompt="Analyze this data: [1,2,3,4,5]",
                max_output_token=200,
                callback=callback,
            )
            service.submit_async(
                scene_id="background",
                prompt="Process this dataset...",
                max_output_token=500,
                callback=callback,
            )

            print("   ✓ 3 async requests submitted")

            print("\n3. Waiting for responses...")
            timeout = 5.0
            start = time.time()
            while len(results) < 3 and time.time() - start < timeout:
                time.sleep(0.1)

            print(f"   ✓ Completed: {len(results)} requests")

            print("\n4. Getting stats...")
            stats = service.get_stats()
            print(f"   Resource usage: {stats['resource']['used_tokens']}/{stats['resource']['total_tokens']} tokens")
            print(f"   Concurrent requests: {stats['resource']['used_concurrent_requests']}")
            if stats['system']:
                print(f"   Load level: {stats['system']['load_level']}")

        print("\n" + "=" * 80)
        print("Service is running. Press Ctrl+C to stop.")
        print("=" * 80)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nReceived shutdown signal...")
    finally:
        service.stop()
        print("✓ Service shutdown complete")


if __name__ == "__main__":
    main()
