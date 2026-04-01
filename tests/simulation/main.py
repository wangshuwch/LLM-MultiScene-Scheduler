#!/usr/bin/env python3

import argparse
import sys
import os
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.simulation.orchestrator import SimulationOrchestrator, SimulationConfig
from tests.simulation.scenarios import get_all_scenarios, get_scenario_by_id, TestScenario


def print_summary(results: List[Dict]) -> None:
    print("\n" + "="*80)
    print("SIMULATION SUMMARY".center(80))
    print("="*80)
    
    print(f"\n{'Scenario':<40} {'Requests':>10} {'Success':>10} {'Avg(ms)':>10} {'P95(ms)':>10}")
    print("-"*80)
    
    for result in results:
        sim_result = result["result"]
        scenario = result["scenario"]
        print(
            f"{scenario.name:<40} "
            f"{sim_result.overall_success_rate.total_requests:>10} "
            f"{sim_result.overall_success_rate.success_rate*100:>9.1f}% "
            f"{sim_result.overall_response_time.avg_ms:>10.1f} "
            f"{sim_result.overall_response_time.p95_ms:>10.1f}"
        )
    
    print("-"*80)


def run_all_scenarios(time_scale: float = 10.0, output_dir: str = "simulation_results") -> List[Dict]:
    print("Starting comprehensive simulation test suite...")
    print(f"Time scale: {time_scale}x")
    print(f"Output directory: {output_dir}")
    
    config = SimulationConfig(
        time_scale=time_scale,
        output_dir=output_dir,
        enable_visualization=True,
        random_seed=42
    )
    
    orchestrator = SimulationOrchestrator(config)
    scenarios = get_all_scenarios()
    
    print(f"\nFound {len(scenarios)} test scenarios:")
    for scenario in scenarios:
        print(f"  - {scenario.scenario_id}: {scenario.name}")
    
    results = orchestrator.run_multiple_scenarios(scenarios)
    
    print_summary(results)
    
    return results


def run_single_scenario(scenario_id: str, time_scale: float = 10.0, output_dir: str = "simulation_results") -> Dict:
    print(f"Running single scenario: {scenario_id}")
    
    scenario = get_scenario_by_id(scenario_id)
    if not scenario:
        print(f"Error: Scenario '{scenario_id}' not found!")
        print("Available scenarios:")
        for s in get_all_scenarios():
            print(f"  - {s.scenario_id}: {s.name}")
        sys.exit(1)
    
    config = SimulationConfig(
        time_scale=time_scale,
        output_dir=output_dir,
        enable_visualization=True,
        random_seed=42
    )
    
    orchestrator = SimulationOrchestrator(config)
    result = orchestrator.run_scenario(scenario)
    
    print_summary([result])
    
    return result


def list_scenarios() -> None:
    print("Available test scenarios:")
    print()
    for scenario in get_all_scenarios():
        print(f"  {scenario.scenario_id}:")
        print(f"    Name: {scenario.name}")
        print(f"    Description: {scenario.description}")
        print(f"    Duration: {scenario.duration_seconds} seconds")
        print(f"    Expected success rate: {scenario.expected_success_rate*100:.1f}%")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="LLM Multi-Scene Scheduler Simulation Test System"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    all_parser = subparsers.add_parser("all", help="Run all test scenarios")
    all_parser.add_argument(
        "--time-scale", "-t", type=float, default=10.0,
        help="Time scale factor (default: 10.0, faster simulation)"
    )
    all_parser.add_argument(
        "--output-dir", "-o", type=str, default="simulation_results",
        help="Output directory for results (default: simulation_results)"
    )
    
    single_parser = subparsers.add_parser("single", help="Run a single test scenario")
    single_parser.add_argument(
        "scenario_id", type=str,
        help="Scenario ID to run (e.g., scenario_a)"
    )
    single_parser.add_argument(
        "--time-scale", "-t", type=float, default=10.0,
        help="Time scale factor (default: 10.0)"
    )
    single_parser.add_argument(
        "--output-dir", "-o", type=str, default="simulation_results",
        help="Output directory for results (default: simulation_results)"
    )
    
    list_parser = subparsers.add_parser("list", help="List all available scenarios")
    
    args = parser.parse_args()
    
    if args.command == "all":
        run_all_scenarios(
            time_scale=args.time_scale,
            output_dir=args.output_dir
        )
    elif args.command == "single":
        run_single_scenario(
            scenario_id=args.scenario_id,
            time_scale=args.time_scale,
            output_dir=args.output_dir
        )
    elif args.command == "list":
        list_scenarios()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
