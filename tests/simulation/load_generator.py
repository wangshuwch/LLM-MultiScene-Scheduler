from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
import random
import math
from datetime import datetime, timedelta

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class TrafficPattern(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    RANDOM = "random"
    SINUSOIDAL = "sinusoidal"
    BURST = "burst"
    STEADY = "steady"


@dataclass
class LoadRequest:
    request_id: str
    scene_id: str
    timestamp: float
    token_estimate: int
    priority: int = 1
    metadata: Dict = field(default_factory=dict)


@dataclass
class LoadProfile:
    name: str
    base_requests_per_second: float
    traffic_pattern: TrafficPattern
    duration_seconds: float
    pattern_params: Dict = field(default_factory=dict)
    token_distribution: Optional[Callable[[], int]] = None
    scene_distribution: Optional[Dict[str, float]] = None


class TrafficPatternGenerator:
    @staticmethod
    def linear(t: float, duration: float, base: float, params: Dict) -> float:
        start_rate = params.get("start_rate", base * 0.5)
        end_rate = params.get("end_rate", base * 2.0)
        return start_rate + (end_rate - start_rate) * (t / duration)

    @staticmethod
    def exponential(t: float, duration: float, base: float, params: Dict) -> float:
        growth_rate = params.get("growth_rate", 1.5)
        peak_time = params.get("peak_time", duration * 0.5)
        if t <= peak_time:
            return base * (growth_rate ** (t / peak_time * 4))
        else:
            return base * (growth_rate ** ((duration - t) / (duration - peak_time) * 4))

    @staticmethod
    def random(t: float, duration: float, base: float, params: Dict) -> float:
        min_factor = params.get("min_factor", 0.5)
        max_factor = params.get("max_factor", 2.0)
        return base * random.uniform(min_factor, max_factor)

    @staticmethod
    def sinusoidal(t: float, duration: float, base: float, params: Dict) -> float:
        amplitude = params.get("amplitude", base * 0.8)
        frequency = params.get("frequency", 2 * math.pi / duration)
        return base + amplitude * math.sin(frequency * t)

    @staticmethod
    def burst(t: float, duration: float, base: float, params: Dict) -> float:
        burst_times = params.get("burst_times", [duration * 0.25, duration * 0.5, duration * 0.75])
        burst_duration = params.get("burst_duration", 5.0)
        burst_multiplier = params.get("burst_multiplier", 5.0)
        
        for burst_t in burst_times:
            if burst_t - burst_duration/2 <= t <= burst_t + burst_duration/2:
                return base * burst_multiplier
        return base

    @staticmethod
    def steady(t: float, duration: float, base: float, params: Dict) -> float:
        return base

    @classmethod
    def generate(cls, pattern: TrafficPattern, t: float, duration: float, base: float, params: Dict) -> float:
        generators = {
            TrafficPattern.LINEAR: cls.linear,
            TrafficPattern.EXPONENTIAL: cls.exponential,
            TrafficPattern.RANDOM: cls.random,
            TrafficPattern.SINUSOIDAL: cls.sinusoidal,
            TrafficPattern.BURST: cls.burst,
            TrafficPattern.STEADY: cls.steady,
        }
        return generators.get(pattern, cls.steady)(t, duration, base, params)


class TokenDistribution:
    @staticmethod
    def uniform(min_tokens: int = 100, max_tokens: int = 4000) -> Callable[[], int]:
        def generator() -> int:
            return random.randint(min_tokens, max_tokens)
        return generator

    @staticmethod
    def normal(mean: int = 1000, std: int = 500, min_tokens: int = 50, max_tokens: int = 8000) -> Callable[[], int]:
        def generator() -> int:
            tokens = int(random.normalvariate(mean, std))
            return max(min_tokens, min(max_tokens, tokens))
        return generator

    @staticmethod
    def long_tail(small_weight: float = 0.7, small_tokens: int = 500, large_tokens: int = 4000) -> Callable[[], int]:
        def generator() -> int:
            if random.random() < small_weight:
                return random.randint(50, small_tokens)
            else:
                return random.randint(small_tokens + 1, large_tokens)
        return generator

    @staticmethod
    def bimodal(peak1: int = 300, peak2: int = 3000, std1: int = 100, std2: int = 800) -> Callable[[], int]:
        def generator() -> int:
            if random.random() < 0.5:
                return max(50, int(random.normalvariate(peak1, std1)))
            else:
                return max(50, int(random.normalvariate(peak2, std2)))
        return generator


class LoadGenerator:
    def __init__(self, profile: LoadProfile):
        self.profile = profile
        self.request_counter = 0
        self._default_token_gen = TokenDistribution.normal()
        self._default_scene_dist = {"default": 1.0}

    def _get_token_estimate(self) -> int:
        if self.profile.token_distribution:
            return self.profile.token_distribution()
        return self._default_token_gen()

    def _get_scene_id(self) -> str:
        if self.profile.scene_distribution:
            scenes = list(self.profile.scene_distribution.keys())
            weights = list(self.profile.scene_distribution.values())
            return random.choices(scenes, weights=weights, k=1)[0]
        return "default"

    def generate_requests_at_time(self, t: float) -> List[LoadRequest]:
        rate = TrafficPatternGenerator.generate(
            self.profile.traffic_pattern,
            t,
            self.profile.duration_seconds,
            self.profile.base_requests_per_second,
            self.profile.pattern_params
        )
        
        if HAS_NUMPY:
            num_requests = np.random.poisson(rate)
        else:
            num_requests = int(round(rate))
        
        requests = []
        
        for _ in range(num_requests):
            self.request_counter += 1
            request = LoadRequest(
                request_id=f"req-{self.request_counter:08d}",
                scene_id=self._get_scene_id(),
                timestamp=t,
                token_estimate=self._get_token_estimate(),
                priority=random.randint(1, 5)
            )
            requests.append(request)
        
        return requests

    def generate_full_trace(self, time_step: float = 1.0) -> Dict[float, List[LoadRequest]]:
        trace = {}
        t = 0.0
        while t < self.profile.duration_seconds:
            requests = self.generate_requests_at_time(t)
            if requests:
                trace[t] = requests
            t += time_step
        return trace

    def get_rate_at_time(self, t: float) -> float:
        return TrafficPatternGenerator.generate(
            self.profile.traffic_pattern,
            t,
            self.profile.duration_seconds,
            self.profile.base_requests_per_second,
            self.profile.pattern_params
        )


def create_load_profile(
    name: str,
    pattern: TrafficPattern,
    base_rps: float = 10.0,
    duration: float = 3600.0,
    scenes: Optional[Dict[str, float]] = None,
    token_dist: Optional[str] = "normal"
) -> LoadProfile:
    scene_dist = scenes or {"scene_1": 0.4, "scene_2": 0.3, "scene_3": 0.3}
    
    token_generators = {
        "uniform": TokenDistribution.uniform(),
        "normal": TokenDistribution.normal(),
        "long_tail": TokenDistribution.long_tail(),
        "bimodal": TokenDistribution.bimodal(),
    }
    
    return LoadProfile(
        name=name,
        base_requests_per_second=base_rps,
        traffic_pattern=pattern,
        duration_seconds=duration,
        scene_distribution=scene_dist,
        token_distribution=token_generators.get(token_dist, TokenDistribution.normal())
    )
