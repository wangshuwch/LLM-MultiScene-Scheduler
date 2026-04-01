from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
import threading
import time
import statistics


class RequestStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class RequestRecord:
    request_id: str
    scene_id: str
    timestamp: float
    token_estimate: int
    status: RequestStatus = RequestStatus.PENDING
    enqueue_time: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    queue_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    total_time_ms: float = 0.0
    error_message: Optional[str] = None
    instance_id: Optional[str] = None


@dataclass
class ResponseTimeMetrics:
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p75_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = 0.0
    count: int = 0


@dataclass
class SuccessRateMetrics:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    timeout: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0


@dataclass
class ResourceMetrics:
    timestamp: float
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    network_utilization: float = 0.0
    active_instances: int = 0
    busy_instances: int = 0
    overloaded_instances: int = 0


@dataclass
class SchedulingMetrics:
    avg_scheduling_latency_ms: float = 0.0
    p95_scheduling_latency_ms: float = 0.0
    scheduling_accuracy: float = 0.0
    queue_backlog: int = 0
    avg_queue_time_ms: float = 0.0


@dataclass
class ThroughputMetrics:
    requests_per_second: float = 0.0
    tokens_per_second: float = 0.0
    peak_rps: float = 0.0
    total_requests: int = 0
    total_tokens: int = 0


@dataclass
class SceneMetrics:
    scene_id: str
    response_time: ResponseTimeMetrics = field(default_factory=ResponseTimeMetrics)
    success_rate: SuccessRateMetrics = field(default_factory=SuccessRateMetrics)
    throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)


@dataclass
class SimulationResult:
    scenario_id: str
    scenario_name: str
    start_time: float
    end_time: float
    duration_seconds: float
    overall_response_time: ResponseTimeMetrics = field(default_factory=ResponseTimeMetrics)
    overall_success_rate: SuccessRateMetrics = field(default_factory=SuccessRateMetrics)
    overall_throughput: ThroughputMetrics = field(default_factory=ThroughputMetrics)
    scheduling_metrics: SchedulingMetrics = field(default_factory=SchedulingMetrics)
    resource_history: List[ResourceMetrics] = field(default_factory=list)
    scene_metrics: Dict[str, SceneMetrics] = field(default_factory=dict)
    request_records: List[RequestRecord] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class MetricsCollector:
    def __init__(self):
        self._lock = threading.RLock()
        self._request_records: Dict[str, RequestRecord] = {}
        self._resource_history: List[ResourceMetrics] = []
        self._scene_ids: Set[str] = set()
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self) -> None:
        with self._lock:
            self._start_time = time.time()

    def stop(self) -> None:
        with self._lock:
            self._end_time = time.time()

    def record_request(self, record: RequestRecord) -> None:
        with self._lock:
            self._request_records[record.request_id] = record
            self._scene_ids.add(record.scene_id)

    def update_request_status(
        self,
        request_id: str,
        status: RequestStatus,
        **kwargs
    ) -> None:
        with self._lock:
            if request_id not in self._request_records:
                return
            record = self._request_records[request_id]
            record.status = status
            
            current_time = time.time()
            
            if status == RequestStatus.QUEUED:
                record.enqueue_time = kwargs.get("enqueue_time", current_time)
            elif status == RequestStatus.EXECUTING:
                record.start_time = kwargs.get("start_time", current_time)
                if record.enqueue_time:
                    record.queue_time_ms = (record.start_time - record.enqueue_time) * 1000
            elif status in [RequestStatus.COMPLETED, RequestStatus.FAILED, RequestStatus.TIMEOUT]:
                record.end_time = kwargs.get("end_time", current_time)
                if record.start_time:
                    record.execution_time_ms = (record.end_time - record.start_time) * 1000
                if record.enqueue_time:
                    record.total_time_ms = (record.end_time - record.enqueue_time) * 1000
                record.error_message = kwargs.get("error_message")
                record.instance_id = kwargs.get("instance_id")

    def record_resource_usage(self, metrics: ResourceMetrics) -> None:
        with self._lock:
            self._resource_history.append(metrics)

    def _calculate_response_time_metrics(self, records: List[RequestRecord]) -> ResponseTimeMetrics:
        times = [r.total_time_ms for r in records if r.total_time_ms > 0]
        if not times:
            return ResponseTimeMetrics()
        
        times.sort()
        return ResponseTimeMetrics(
            avg_ms=statistics.mean(times),
            p50_ms=times[int(len(times) * 0.5)],
            p75_ms=times[int(len(times) * 0.75)],
            p95_ms=times[int(len(times) * 0.95)],
            p99_ms=times[int(len(times) * 0.99)],
            max_ms=times[-1],
            min_ms=times[0],
            count=len(times)
        )

    def _calculate_success_rate_metrics(self, records: List[RequestRecord]) -> SuccessRateMetrics:
        total = len(records)
        if total == 0:
            return SuccessRateMetrics()
        
        successful = sum(1 for r in records if r.status == RequestStatus.COMPLETED)
        failed = sum(1 for r in records if r.status == RequestStatus.FAILED)
        timeout = sum(1 for r in records if r.status == RequestStatus.TIMEOUT)
        
        return SuccessRateMetrics(
            total_requests=total,
            successful=successful,
            failed=failed,
            timeout=timeout,
            success_rate=successful / total if total > 0 else 0.0,
            failure_rate=(failed + timeout) / total if total > 0 else 0.0
        )

    def _calculate_throughput_metrics(self, records: List[RequestRecord], duration: float) -> ThroughputMetrics:
        if duration <= 0:
            return ThroughputMetrics()
        
        total_requests = len(records)
        total_tokens = sum(r.token_estimate for r in records)
        
        rps = total_requests / duration
        tps = total_tokens / duration
        
        return ThroughputMetrics(
            requests_per_second=rps,
            tokens_per_second=tps,
            peak_rps=rps,
            total_requests=total_requests,
            total_tokens=total_tokens
        )

    def _calculate_scheduling_metrics(self, records: List[RequestRecord]) -> SchedulingMetrics:
        queue_times = [r.queue_time_ms for r in records if r.queue_time_ms > 0]
        if not queue_times:
            return SchedulingMetrics()
        
        queue_times.sort()
        return SchedulingMetrics(
            avg_scheduling_latency_ms=statistics.mean(queue_times),
            p95_scheduling_latency_ms=queue_times[int(len(queue_times) * 0.95)] if len(queue_times) > 20 else queue_times[-1],
            scheduling_accuracy=1.0,
            queue_backlog=0,
            avg_queue_time_ms=statistics.mean(queue_times)
        )

    def get_result(self, scenario_id: str, scenario_name: str) -> SimulationResult:
        with self._lock:
            records = list(self._request_records.values())
            duration = (self._end_time or time.time()) - (self._start_time or time.time())
            
            result = SimulationResult(
                scenario_id=scenario_id,
                scenario_name=scenario_name,
                start_time=self._start_time or 0,
                end_time=self._end_time or 0,
                duration_seconds=duration,
                resource_history=self._resource_history.copy(),
                request_records=records.copy()
            )
            
            result.overall_response_time = self._calculate_response_time_metrics(records)
            result.overall_success_rate = self._calculate_success_rate_metrics(records)
            result.overall_throughput = self._calculate_throughput_metrics(records, duration)
            result.scheduling_metrics = self._calculate_scheduling_metrics(records)
            
            for scene_id in self._scene_ids:
                scene_records = [r for r in records if r.scene_id == scene_id]
                scene_metrics = SceneMetrics(
                    scene_id=scene_id,
                    response_time=self._calculate_response_time_metrics(scene_records),
                    success_rate=self._calculate_success_rate_metrics(scene_records),
                    throughput=self._calculate_throughput_metrics(scene_records, duration)
                )
                result.scene_metrics[scene_id] = scene_metrics
            
            return result

    def reset(self) -> None:
        with self._lock:
            self._request_records.clear()
            self._resource_history.clear()
            self._scene_ids.clear()
            self._start_time = None
            self._end_time = None
