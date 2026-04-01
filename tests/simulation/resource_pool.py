from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import threading
import time
import random


class ServiceStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    UNAVAILABLE = "unavailable"


@dataclass
class LLMServiceInstance:
    instance_id: str
    processing_power: float
    memory_limit_gb: float
    base_latency_ms: float
    max_concurrent_requests: int
    status: ServiceStatus = ServiceStatus.IDLE
    current_concurrent: int = 0
    used_memory_gb: float = 0.0
    total_requests_processed: int = 0
    total_errors: int = 0

    def can_accept_request(self) -> bool:
        if self.status == ServiceStatus.UNAVAILABLE:
            return False
        return self.current_concurrent < self.max_concurrent_requests

    def get_current_latency(self) -> float:
        load_factor = self.current_concurrent / self.max_concurrent_requests
        latency_multiplier = 1.0 + (load_factor * 2.0)
        return self.base_latency_ms * latency_multiplier

    def accept_request(self) -> bool:
        if not self.can_accept_request():
            return False
        self.current_concurrent += 1
        if self.current_concurrent >= self.max_concurrent_requests * 0.8:
            self.status = ServiceStatus.OVERLOADED
        elif self.current_concurrent > 0:
            self.status = ServiceStatus.BUSY
        return True

    def release_request(self, success: bool = True) -> None:
        if self.current_concurrent > 0:
            self.current_concurrent -= 1
        self.total_requests_processed += 1
        if not success:
            self.total_errors += 1
        if self.current_concurrent == 0:
            self.status = ServiceStatus.IDLE
        elif self.current_concurrent < self.max_concurrent_requests * 0.5:
            self.status = ServiceStatus.BUSY


@dataclass
class ResourceUsageSnapshot:
    timestamp: float
    total_instances: int
    busy_instances: int
    overloaded_instances: int
    total_concurrent_requests: int
    total_memory_used_gb: float
    total_processing_power: float
    used_processing_power: float


class ResourcePoolManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._instances: Dict[str, LLMServiceInstance] = {}
        self._usage_history: List[ResourceUsageSnapshot] = []
        self._start_time: Optional[float] = None

    def add_instance(self, instance: LLMServiceInstance) -> None:
        with self._lock:
            self._instances[instance.instance_id] = instance

    def remove_instance(self, instance_id: str) -> bool:
        with self._lock:
            if instance_id in self._instances:
                del self._instances[instance_id]
                return True
            return False

    def get_available_instance(self) -> Optional[LLMServiceInstance]:
        with self._lock:
            available = [
                inst for inst in self._instances.values()
                if inst.can_accept_request()
            ]
            if not available:
                return None
            return min(available, key=lambda x: x.current_concurrent)

    def allocate_instance(self) -> Optional[LLMServiceInstance]:
        with self._lock:
            instance = self.get_available_instance()
            if instance and instance.accept_request():
                return instance
            return None

    def release_instance(self, instance_id: str, success: bool = True) -> None:
        with self._lock:
            if instance_id in self._instances:
                self._instances[instance_id].release_request(success)

    def get_snapshot(self) -> ResourceUsageSnapshot:
        with self._lock:
            total = len(self._instances)
            busy = sum(1 for inst in self._instances.values() if inst.status == ServiceStatus.BUSY)
            overloaded = sum(1 for inst in self._instances.values() if inst.status == ServiceStatus.OVERLOADED)
            total_concurrent = sum(inst.current_concurrent for inst in self._instances.values())
            total_memory = sum(inst.used_memory_gb for inst in self._instances.values())
            total_power = sum(inst.processing_power for inst in self._instances.values())
            used_power = sum(inst.processing_power * (inst.current_concurrent / max(1, inst.max_concurrent_requests))
                            for inst in self._instances.values())
            return ResourceUsageSnapshot(
                timestamp=time.time(),
                total_instances=total,
                busy_instances=busy,
                overloaded_instances=overloaded,
                total_concurrent_requests=total_concurrent,
                total_memory_used_gb=total_memory,
                total_processing_power=total_power,
                used_processing_power=used_power
            )

    def record_usage(self) -> None:
        with self._lock:
            snapshot = self.get_snapshot()
            self._usage_history.append(snapshot)

    def get_usage_history(self) -> List[ResourceUsageSnapshot]:
        with self._lock:
            return self._usage_history.copy()

    def get_total_capacity(self) -> int:
        with self._lock:
            return sum(inst.max_concurrent_requests for inst in self._instances.values())

    def get_current_utilization(self) -> float:
        with self._lock:
            total_capacity = self.get_total_capacity()
            if total_capacity == 0:
                return 0.0
            current_usage = sum(inst.current_concurrent for inst in self._instances.values())
            return current_usage / total_capacity

    def reset(self) -> None:
        with self._lock:
            for instance in self._instances.values():
                instance.current_concurrent = 0
                instance.status = ServiceStatus.IDLE
                instance.total_requests_processed = 0
                instance.total_errors = 0
            self._usage_history = []


def create_default_resource_pool() -> ResourcePoolManager:
    pool = ResourcePoolManager()
    
    instance_configs = [
        ("llm-001", 1.0, 16.0, 100.0, 50),
        ("llm-002", 1.0, 16.0, 100.0, 50),
        ("llm-003", 1.5, 24.0, 80.0, 75),
        ("llm-004", 1.5, 24.0, 80.0, 75),
        ("llm-005", 2.0, 32.0, 60.0, 100),
    ]
    
    for instance_id, power, memory, latency, max_concurrent in instance_configs:
        pool.add_instance(LLMServiceInstance(
            instance_id=instance_id,
            processing_power=power,
            memory_limit_gb=memory,
            base_latency_ms=latency,
            max_concurrent_requests=max_concurrent
        ))
    
    return pool
