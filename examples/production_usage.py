import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from datetime import timedelta
from typing import Optional

from src.models import SceneConfig, LLMRequest, GlobalConfig
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator
from src.state_analyzer import SchedulingStrategyConfig


def create_production_scheduler(
    use_real_llm: bool = False,
    openai_api_key: Optional[str] = None,
    openai_model: str = "gpt-3.5-turbo",
):
    print("=" * 80)
    print("LLM Multi-Scene Scheduler - Production Usage Example")
    print("=" * 80)

    global_config = GlobalConfig(
        total_concurrent_tokens=100000,
        global_tpm=1000000,
        global_qpm=10000,
        window_size_seconds=60,
        window_step_seconds=1,
        worker_count=5,
        max_concurrent_requests=50,
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
            max_concurrent_requests=30,
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
            max_concurrent_requests=15,
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
            max_concurrent_requests=10,
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

    scheduler = Scheduler(
        config=scheduler_config,
        llm_client=llm_client,
        token_estimator=SimpleEstimator(),
        scheduling_strategy_config=strategy_config,
    )

    return scheduler


def run_examples(scheduler: Scheduler):
    print("\n" + "=" * 80)
    print("Starting scheduler...")
    print("=" * 80)
    scheduler.start()
    time.sleep(0.1)

    print("\n1. Testing synchronous request (Chatbot)...")
    req1 = LLMRequest(
        scene_id="chatbot",
        prompt="Hello, how can I help you today?",
        max_output_token=100,
    )
    try:
        resp1 = scheduler.submit(req1)
        print(f"   ✓ Response: {resp1.content[:80]}...")
        print(f"   ✓ Tokens used: {resp1.tokens_used}")
        print(f"   ✓ Duration: {resp1.duration.total_seconds():.2f}s")
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    print("\n2. Testing async requests (mixed scenes)...")
    results = []
    result_lock = threading.Lock()

    def callback(resp, err):
        with result_lock:
            results.append((resp, err))

    req2 = LLMRequest(
        scene_id="chatbot",
        prompt="What's the weather like today?",
        max_output_token=100,
    )
    req3 = LLMRequest(
        scene_id="analytics",
        prompt="Analyze this data: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
        max_output_token=200,
    )
    req4 = LLMRequest(
        scene_id="background",
        prompt="Process this large dataset...",
        max_output_token=500,
    )

    try:
        scheduler.submit_async(req2, callback)
        scheduler.submit_async(req3, callback)
        scheduler.submit_async(req4, callback)
        print("   ✓ 3 async requests submitted")
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")

    print("\n3. Waiting for async requests to complete...")
    timeout = 5.0
    start = time.time()
    while len(results) < 3 and time.time() - start < timeout:
        time.sleep(0.1)

    print(f"   ✓ Completed: {len(results)} requests")
    for i, (resp, err) in enumerate(results):
        if err:
            print(f"   Request {i+1} failed: {err}")
        else:
            print(f"   Request {i+1} succeeded: {resp.content[:50]}...")

    print("\n4. Checking resource state...")
    resource_state = scheduler.get_resource_state()
    print(f"   Total tokens: {resource_state.total_concurrent_tokens}")
    print(f"   Used tokens: {resource_state.used_concurrent_tokens}")
    print(f"   Available tokens: {resource_state.available_concurrent_tokens}")
    print(f"   Used concurrent requests: {resource_state.used_concurrent_requests}")
    print(f"   Scene usage: {resource_state.scene_concurrent_usage}")

    print("\n5. Checking queue states...")
    queue_states = scheduler.get_queue_states()
    for qs in queue_states:
        print(f"   Scene {qs.scene_id}:")
        print(f"     Queue length: {qs.queue_length}")
        print(f"     Waiting tokens: {qs.waiting_tokens}")

    print("\n6. Checking rate limit state...")
    rate_limit_state = scheduler.get_rate_limit_state()
    print(f"   Global TPM used: {rate_limit_state.global_tpm_used}")
    print(f"   Global QPM used: {rate_limit_state.global_qpm_used}")
    print(f"   Scene TPM used: {rate_limit_state.scene_tpm_used}")
    print(f"   Scene QPM used: {rate_limit_state.scene_qpm_used}")

    print("\n7. Checking system state...")
    system_state = scheduler.get_last_system_state()
    if system_state:
        print(f"   Load level: {system_state.load_level}")
        print(f"   Bottleneck resource: {system_state.bottleneck_resource}")
        print(f"   Resource utilization: {system_state.resource_utilization:.2%}")

    print("\n" + "=" * 80)
    print("Stopping scheduler...")
    print("=" * 80)
    scheduler.stop()


if __name__ == "__main__":
    import threading
    import argparse

    parser = argparse.ArgumentParser(description="LLM Multi-Scene Scheduler - Production Usage")
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

    args = parser.parse_args()

    scheduler = create_production_scheduler(
        use_real_llm=args.use_real_llm,
        openai_api_key=args.api_key,
        openai_model=args.model,
    )

    run_examples(scheduler)

    print("\n" + "=" * 80)
    print("Example completed successfully!")
    print("=" * 80)
