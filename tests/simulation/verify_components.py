#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


def test_resource_pool():
    print("Testing Resource Pool...")
    from tests.simulation.resource_pool import (
        ServiceStatus,
        LLMServiceInstance,
        ResourcePoolManager,
        create_default_resource_pool
    )
    
    pool = create_default_resource_pool()
    print(f"  ✓ Created resource pool with {len(pool._instances)} instances")
    
    instance = pool.allocate_instance()
    print(f"  ✓ Allocated instance: {instance.instance_id if instance else 'None'}")
    
    if instance:
        pool.release_instance(instance.instance_id, True)
        print(f"  ✓ Released instance: {instance.instance_id}")
    
    snapshot = pool.get_snapshot()
    print(f"  ✓ Got snapshot - Total: {snapshot.total_instances}, "
          f"Busy: {snapshot.busy_instances}, "
          f"Overloaded: {snapshot.overloaded_instances}")
    
    print("✓ Resource Pool tests passed!")
    return True


def test_load_generator():
    print("\nTesting Load Generator...")
    from tests.simulation.load_generator import (
        TrafficPattern,
        LoadProfile,
        LoadGenerator,
        TokenDistribution
    )
    
    profile = LoadProfile(
        name="test",
        base_requests_per_second=5.0,
        traffic_pattern=TrafficPattern.STEADY,
        duration_seconds=10.0,
        scene_distribution={"test_scene": 1.0},
        token_distribution=TokenDistribution.normal()
    )
    
    generator = LoadGenerator(profile)
    requests = generator.generate_requests_at_time(0.0)
    print(f"  ✓ Generated {len(requests)} requests at time 0.0")
    
    for req in requests[:3]:
        print(f"    - Request {req.request_id}: scene={req.scene_id}, tokens={req.token_estimate}")
    
    print("✓ Load Generator tests passed!")
    return True


def test_scenarios():
    print("\nTesting Scenarios...")
    from tests.simulation.scenarios import get_all_scenarios, get_scenario_by_id
    
    scenarios = get_all_scenarios()
    print(f"  ✓ Found {len(scenarios)} test scenarios")
    
    for scenario in scenarios:
        print(f"    - {scenario.scenario_id}: {scenario.name}")
    
    scenario_c = get_scenario_by_id("scenario_c")
    print(f"  ✓ Retrieved scenario_c: {scenario_c.name if scenario_c else 'None'}")
    
    print("✓ Scenarios tests passed!")
    return True


def test_monitoring():
    print("\nTesting Monitoring...")
    from tests.simulation.monitoring import (
        RequestStatus,
        RequestRecord,
        MetricsCollector
    )
    
    collector = MetricsCollector()
    
    record1 = RequestRecord(
        request_id="test-001",
        scene_id="test_scene",
        timestamp=1.0,
        token_estimate=500
    )
    record2 = RequestRecord(
        request_id="test-002",
        scene_id="test_scene",
        timestamp=2.0,
        token_estimate=1000
    )
    
    collector.record_request(record1)
    collector.record_request(record2)
    print(f"  ✓ Recorded 2 requests")
    
    collector.start()
    
    collector.update_request_status(
        "test-001",
        RequestStatus.QUEUED,
        enqueue_time=1.0
    )
    collector.update_request_status(
        "test-001",
        RequestStatus.EXECUTING,
        start_time=1.5
    )
    collector.update_request_status(
        "test-001",
        RequestStatus.COMPLETED,
        end_time=2.0
    )
    
    collector.update_request_status(
        "test-002",
        RequestStatus.QUEUED,
        enqueue_time=2.0
    )
    collector.update_request_status(
        "test-002",
        RequestStatus.EXECUTING,
        start_time=2.2
    )
    collector.update_request_status(
        "test-002",
        RequestStatus.COMPLETED,
        end_time=3.0
    )
    
    collector.stop()
    
    result = collector.get_result("test_scenario", "Test Scenario")
    print(f"  ✓ Got result - Total requests: {result.overall_success_rate.total_requests}")
    print(f"  ✓ Success rate: {result.overall_success_rate.success_rate*100:.1f}%")
    print(f"  ✓ Avg response: {result.overall_response_time.avg_ms:.1f}ms")
    
    print("✓ Monitoring tests passed!")
    return True


def test_visualization():
    print("\nTesting Visualization...")
    from tests.simulation.visualization import VisualizationConfig, ReportGenerator
    
    config = VisualizationConfig(output_dir="test_vis_output")
    generator = ReportGenerator(config)
    
    print(f"  ✓ Created ReportGenerator with output dir: {config.output_dir}")
    
    print("✓ Visualization tests passed!")
    return True


def test_orchestrator():
    print("\nTesting Orchestrator...")
    from tests.simulation.orchestrator import SimulationConfig, SimulationOrchestrator
    
    config = SimulationConfig(
        time_scale=100.0,
        output_dir="test_orch_output",
        enable_visualization=False,
        random_seed=42
    )
    
    orchestrator = SimulationOrchestrator(config)
    print(f"  ✓ Created SimulationOrchestrator")
    
    print("✓ Orchestrator tests passed!")
    return True


def main():
    print("=" * 80)
    print("LLM Multi-Scene Scheduler - Simulation Test System Component Verification")
    print("=" * 80)
    
    tests = [
        ("Resource Pool", test_resource_pool),
        ("Load Generator", test_load_generator),
        ("Scenarios", test_scenarios),
        ("Monitoring", test_monitoring),
        ("Visualization", test_visualization),
        ("Orchestrator", test_orchestrator),
    ]
    
    all_passed = True
    
    for name, test_func in tests:
        try:
            passed = test_func()
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"\n✗ {name} tests failed!")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ All component tests passed!")
    else:
        print("✗ Some tests failed!")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
