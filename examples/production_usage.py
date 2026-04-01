import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from datetime import timedelta

from src.models import SceneConfig, LLMRequest, GlobalConfig
from src.scheduler import Scheduler, SchedulerConfig
from src.token_estimator import SimpleEstimator
from src.clients import OpenAIClient


def main():
    print("=" * 60)
    print("LLM Multi-Scene Scheduler - Production Usage Example")
    print("=" * 60)

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
            max_concurrent_requests=25,
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
            max_concurrent_requests=20,
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
            max_concurrent_requests=15,
        ),
    ]

    scheduler_config = SchedulerConfig(
        global_config=global_config,
        scene_configs=scene_configs,
        cleanup_interval=30.0,
        dispatch_interval=0.01,
        global_queue_size=10000,
    )

    llm_client = OpenAIClient(
        model="gpt-3.5-turbo",
        temperature=0.7,
    )

    scheduler = Scheduler(
        config=scheduler_config,
        llm_client=llm_client,
        token_estimator=SimpleEstimator(),
    )

    print("\nStarting scheduler...")
    scheduler.start()
    time.sleep(0.1)

    print("\n1. Testing synchronous request...")
    req1 = LLMRequest(
        scene_id="chatbot",
        prompt="Hello, how are you?",
        max_output_token=100,
    )
    try:
        resp1 = scheduler.submit(req1)
        print("   Response:", resp1.content)
        print("   Tokens used:", resp1.tokens_used)
        print("   Duration:", str(resp1.duration.total_seconds()) + "s")
    except Exception as e:
        print("   Error:", str(e))

    print("\n2. Testing asynchronous requests...")
    results = []
    import threading
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
        prompt="Analyze this data: [1, 2, 3, 4, 5]",
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
        print("   3 async requests submitted")
    except Exception as e:
        print("   Error:", str(e))

    print("\n3. Waiting for async requests to complete...")
    timeout = 10.0
    start = time.time()
    while len(results) < 3 and time.time() - start < timeout:
        time.sleep(0.1)

    print("   Completed:", str(len(results)) + " requests")
    for i, (resp, err) in enumerate(results):
        if err:
            print("   Request", str(i+1), "failed:", str(err))
        else:
            print("   Request", str(i+1), "succeeded:", resp.content[:50] + "...")

    print("\n4. Checking resource state...")
    resource_state = scheduler.get_resource_state()
    print("   Total tokens:", resource_state.total_concurrent_tokens)
    print("   Used tokens:", resource_state.used_concurrent_tokens)
    print("   Available tokens:", resource_state.available_concurrent_tokens)
    print("   Scene usage:", str(resource_state.scene_concurrent_usage))
    print("   Used concurrent requests:", resource_state.used_concurrent_requests)

    print("\n5. Checking queue states...")
    queue_states = scheduler.get_queue_states()
    for qs in queue_states:
        print("   Scene", qs.scene_id + ":")
        print("     Queue length:", qs.queue_length)
        print("     Waiting tokens:", qs.waiting_tokens)

    print("\n6. Checking rate limit state...")
    rate_limit_state = scheduler.get_rate_limit_state()
    print("   Global TPM used:", rate_limit_state.global_tpm_used)
    print("   Global QPM used:", rate_limit_state.global_qpm_used)
    print("   Scene TPM used:", str(rate_limit_state.scene_tpm_used))
    print("   Scene QPM used:", str(rate_limit_state.scene_qpm_used))

    print("\nStopping scheduler...")
    scheduler.stop()

    print("\n" + "=" * 60)
    print("Production example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
