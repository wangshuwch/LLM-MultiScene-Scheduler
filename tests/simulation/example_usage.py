#!/usr/bin/env python3

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.simulation import (
    SimulationOrchestrator,
    SimulationConfig,
    get_all_scenarios,
    create_extreme_burst_scenario
)


def example_basic_usage():
    print("=" * 80)
    print("Example 1: Basic Usage - Run a single scenario")
    print("=" * 80)
    
    config = SimulationConfig(
        time_scale=100.0,
        output_dir="simulation_results_example",
        enable_visualization=True,
        random_seed=42
    )
    
    orchestrator = SimulationOrchestrator(config)
    scenario = create_extreme_burst_scenario()
    
    scenario.duration_seconds = 60
    
    result = orchestrator.run_scenario(scenario)
    
    print(f"\nReport generated at: {result['report_files'].get('html_report', 'N/A')}")
    print()


def example_list_scenarios():
    print("=" * 80)
    print("Example 2: List all available scenarios")
    print("=" * 80)
    
    scenarios = get_all_scenarios()
    print(f"\nFound {len(scenarios)} test scenarios:\n")
    
    for scenario in scenarios:
        print(f"  {scenario.scenario_id}: {scenario.name}")
        print(f"    Description: {scenario.description}")
        print(f"    Duration: {scenario.duration_seconds} seconds")
        print()


def main():
    example_list_scenarios()
    print("\n" + "=" * 80)
    print("To run the simulation, use the command line interface:")
    print("=" * 80)
    print("\n  # List all scenarios")
    print("  python tests/simulation/main.py list")
    print("\n  # Run a single scenario (fast simulation with 100x time scale)")
    print("  python tests/simulation/main.py single scenario_c -t 100")
    print("\n  # Run all scenarios")
    print("  python tests/simulation/main.py all -t 100")
    print()


if __name__ == "__main__":
    main()
