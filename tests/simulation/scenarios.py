from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from .load_generator import (
    LoadProfile,
    TrafficPattern,
    TokenDistribution,
    create_load_profile
)


class ScenarioType(Enum):
    DAYTIME_PEAK = "daytime_peak"
    NIGHTTIME_PEAK = "nighttime_peak"
    EXTREME_BURST = "extreme_burst"
    MIXED_REQUESTS = "mixed_requests"


@dataclass
class TestScenario:
    scenario_id: str
    name: str
    description: str
    scenario_type: ScenarioType
    load_profile: LoadProfile
    duration_seconds: float
    expected_success_rate: float = 0.95
    expected_p95_response_ms: float = 500.0
    resource_pool_config: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)


def create_daytime_peak_scenario() -> TestScenario:
    load_profile = LoadProfile(
        name="daytime_peak",
        base_requests_per_second=25.0,
        traffic_pattern=TrafficPattern.SINUSOIDAL,
        duration_seconds=32400.0,
        pattern_params={
            "amplitude": 20.0,
            "frequency": 2 * 3.14159 / 32400.0
        },
        scene_distribution={
            "chat": 0.4,
            "qa": 0.3,
            "summarization": 0.2,
            "coding": 0.1
        },
        token_distribution=TokenDistribution.normal(mean=800, std=400)
    )
    
    return TestScenario(
        scenario_id="scenario_a",
        name="Daytime Peak (9:00-18:00)",
        description="Simulates typical workday traffic with gradual increase and decrease",
        scenario_type=ScenarioType.DAYTIME_PEAK,
        load_profile=load_profile,
        duration_seconds=32400.0,
        expected_success_rate=0.95,
        expected_p95_response_ms=600.0,
        metadata={
            "start_hour": 9,
            "end_hour": 18,
            "peak_hour": 14
        }
    )


def create_nighttime_peak_scenario() -> TestScenario:
    load_profile = LoadProfile(
        name="nighttime_peak",
        base_requests_per_second=15.0,
        traffic_pattern=TrafficPattern.EXPONENTIAL,
        duration_seconds=10800.0,
        pattern_params={
            "growth_rate": 2.0,
            "peak_time": 5400.0
        },
        scene_distribution={
            "chat": 0.5,
            "qa": 0.25,
            "creative": 0.25
        },
        token_distribution=TokenDistribution.long_tail(
            small_weight=0.8,
            small_tokens=300,
            large_tokens=5000
        )
    )
    
    return TestScenario(
        scenario_id="scenario_b",
        name="Nighttime Peak (23:00-02:00)",
        description="Late night traffic with exponential growth and rapid decline",
        scenario_type=ScenarioType.NIGHTTIME_PEAK,
        load_profile=load_profile,
        duration_seconds=10800.0,
        expected_success_rate=0.98,
        expected_p95_response_ms=400.0,
        metadata={
            "start_hour": 23,
            "end_hour": 2,
            "peak_hour": 0
        }
    )


def create_extreme_burst_scenario() -> TestScenario:
    load_profile = LoadProfile(
        name="extreme_burst",
        base_requests_per_second=10.0,
        traffic_pattern=TrafficPattern.BURST,
        duration_seconds=1800.0,
        pattern_params={
            "burst_times": [300.0, 600.0, 900.0, 1200.0],
            "burst_duration": 60.0,
            "burst_multiplier": 20.0
        },
        scene_distribution={
            "api": 0.6,
            "web": 0.4
        },
        token_distribution=TokenDistribution.uniform(min_tokens=100, max_tokens=2000)
    )
    
    return TestScenario(
        scenario_id="scenario_c",
        name="Extreme Burst",
        description="Multiple extreme traffic bursts to test system resilience",
        scenario_type=ScenarioType.EXTREME_BURST,
        load_profile=load_profile,
        duration_seconds=1800.0,
        expected_success_rate=0.85,
        expected_p95_response_ms=2000.0,
        metadata={
            "num_bursts": 4,
            "burst_interval": 300,
            "burst_intensity": "20x"
        }
    )


def create_mixed_requests_scenario() -> TestScenario:
    load_profile = LoadProfile(
        name="mixed_requests",
        base_requests_per_second=20.0,
        traffic_pattern=TrafficPattern.STEADY,
        duration_seconds=7200.0,
        pattern_params={},
        scene_distribution={
            "small_tasks": 0.6,
            "medium_tasks": 0.25,
            "large_tasks": 0.15
        },
        token_distribution=TokenDistribution.bimodal(
            peak1=200,
            peak2=3500,
            std1=80,
            std2=1000
        )
    )
    
    return TestScenario(
        scenario_id="scenario_d",
        name="Mixed Requests (Long-tail + Small)",
        description="Mix of small quick requests and large long-running requests",
        scenario_type=ScenarioType.MIXED_REQUESTS,
        load_profile=load_profile,
        duration_seconds=7200.0,
        expected_success_rate=0.92,
        expected_p95_response_ms=1500.0,
        metadata={
            "small_ratio": 0.6,
            "large_ratio": 0.15,
            "token_range": "200-3500"
        }
    )


def get_all_scenarios() -> List[TestScenario]:
    return [
        create_daytime_peak_scenario(),
        create_nighttime_peak_scenario(),
        create_extreme_burst_scenario(),
        create_mixed_requests_scenario()
    ]


def get_scenario_by_id(scenario_id: str) -> Optional[TestScenario]:
    scenarios = get_all_scenarios()
    for scenario in scenarios:
        if scenario.scenario_id == scenario_id:
            return scenario
    return None


def get_scenarios_by_type(scenario_type: ScenarioType) -> List[TestScenario]:
    scenarios = get_all_scenarios()
    return [s for s in scenarios if s.scenario_type == scenario_type]


SCENARIO_REGISTRY = {
    "scenario_a": create_daytime_peak_scenario,
    "scenario_b": create_nighttime_peak_scenario,
    "scenario_c": create_extreme_burst_scenario,
    "scenario_d": create_mixed_requests_scenario,
}


def create_scenario(scenario_id: str) -> Optional[TestScenario]:
    creator = SCENARIO_REGISTRY.get(scenario_id)
    if creator:
        return creator()
    return None
