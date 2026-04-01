#!/usr/bin/env python3

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.simulation import (
    SimulationOrchestrator,
    SimulationConfig,
    create_extreme_burst_scenario,
    LoadProfile,
    TrafficPattern,
    TokenDistribution
)


def quick_test():
    print("=" * 80)
    print("Quick Test: Run a short simulation")
    print("=" * 80)
    
    config = SimulationConfig(
        time_scale=100.0,
        output_dir="simulation_results_quick",
        enable_visualization=True,
        random_seed=42
    )
    
    orchestrator = SimulationOrchestrator(config)
    scenario = create_extreme_burst_scenario()
    
    scenario.duration_seconds = 10
    
    print(f"\nRunning scenario: {scenario.name}")
    print(f"Duration: {scenario.duration_seconds} seconds (simulated)")
    print(f"Time scale: {config.time_scale}x")
    print()
    
    try:
        result = orchestrator.run_scenario(scenario)
        
        print(f"\n✓ Simulation completed!")
        print(f"  Report files generated in: {config.output_dir}")
        
        sim_result = result["result"]
        print(f"\nResults Summary:")
        print(f"  Total requests: {sim_result.overall_success_rate.total_requests}")
        print(f"  Success rate: {sim_result.overall_success_rate.success_rate*100:.1f}%")
        print(f"  Avg response: {sim_result.overall_response_time.avg_ms:.1f}ms")
        print(f"  P95 response: {sim_result.overall_response_time.p95_ms:.1f}ms")
        
        print("\n" + "=" * 80)
        print("Quick test completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError during simulation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    quick_test()
