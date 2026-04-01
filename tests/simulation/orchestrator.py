from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import time
import random
from queue import Queue, Empty
from threading import Thread, Lock
from .resource_pool import ResourcePoolManager, create_default_resource_pool
from .load_generator import LoadGenerator, LoadRequest
from .scenarios import TestScenario
from .monitoring import MetricsCollector, RequestRecord, RequestStatus, ResourceMetrics
from .visualization import ReportGenerator, VisualizationConfig


@dataclass
class SimulationConfig:
    time_scale: float = 1.0
    resource_monitor_interval: float = 1.0
    max_queue_size: int = 10000
    enable_visualization: bool = True
    output_dir: str = "simulation_results"
    random_seed: Optional[int] = None


class SimulationOrchestrator:
    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()
        self.resource_pool: Optional[ResourcePoolManager] = None
        self.metrics_collector = MetricsCollector()
        self.report_generator = ReportGenerator(
            VisualizationConfig(output_dir=self.config.output_dir)
        )
        self._request_queue: Queue[LoadRequest] = Queue(maxsize=self.config.max_queue_size)
        self._active_requests: Dict[str, dict] = {}
        self._lock = Lock()
        self._running = False
        self._worker_threads: List[Thread] = []
        self._monitor_thread: Optional[Thread] = None
        self._generator_thread: Optional[Thread] = None
        
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)

    def _initialize_resource_pool(self, scenario: TestScenario) -> None:
        if scenario.resource_pool_config:
            self.resource_pool = ResourcePoolManager()
        else:
            self.resource_pool = create_default_resource_pool()

    def _load_generator_worker(self, scenario: TestScenario, duration: float) -> None:
        generator = LoadGenerator(scenario.load_profile)
        start_time = time.time()
        sim_time = 0.0
        
        while self._running and sim_time < duration:
            requests = generator.generate_requests_at_time(sim_time)
            for req in requests:
                try:
                    self._request_queue.put(req, block=False)
                except:
                    pass
            
            sim_time += 1.0 / self.config.time_scale
            elapsed = time.time() - start_time
            sleep_time = max(0, (sim_time / self.config.time_scale) - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _process_request(self, request: LoadRequest) -> None:
        record = RequestRecord(
            request_id=request.request_id,
            scene_id=request.scene_id,
            timestamp=time.time(),
            token_estimate=request.token_estimate
        )
        self.metrics_collector.record_request(record)
        
        self.metrics_collector.update_request_status(
            request.request_id,
            RequestStatus.QUEUED,
            enqueue_time=time.time()
        )
        
        with self._lock:
            self._active_requests[request.request_id] = {
                "request": request,
                "record": record,
                "start_time": None,
                "instance": None
            }
        
        instance = None
        retry_count = 0
        max_retries = 10
        
        while self._running and retry_count < max_retries and instance is None:
            instance = self.resource_pool.allocate_instance()
            if instance is None:
                time.sleep(0.01)
                retry_count += 1
        
        if instance is None:
            self.metrics_collector.update_request_status(
                request.request_id,
                RequestStatus.FAILED,
                error_message="No available instance",
                end_time=time.time()
            )
            with self._lock:
                if request.request_id in self._active_requests:
                    del self._active_requests[request.request_id]
            return
        
        with self._lock:
            if request.request_id in self._active_requests:
                self._active_requests[request.request_id]["instance"] = instance
                self._active_requests[request.request_id]["start_time"] = time.time()
        
        self.metrics_collector.update_request_status(
            request.request_id,
            RequestStatus.EXECUTING,
            start_time=time.time(),
            instance_id=instance.instance_id
        )
        
        base_latency = instance.get_current_latency()
        token_factor = request.token_estimate / 1000.0
        processing_time = (base_latency * token_factor) / 1000.0 / self.config.time_scale
        processing_time = max(0.01, processing_time)
        
        time.sleep(processing_time)
        
        success = random.random() > 0.01
        
        self.resource_pool.release_instance(instance.instance_id, success)
        
        if success:
            self.metrics_collector.update_request_status(
                request.request_id,
                RequestStatus.COMPLETED,
                end_time=time.time()
            )
        else:
            self.metrics_collector.update_request_status(
                request.request_id,
                RequestStatus.FAILED,
                error_message="Processing error",
                end_time=time.time()
            )
        
        with self._lock:
            if request.request_id in self._active_requests:
                del self._active_requests[request.request_id]

    def _worker_thread_func(self) -> None:
        while self._running:
            try:
                request = self._request_queue.get(timeout=0.1)
                self._process_request(request)
                self._request_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                pass

    def _monitor_thread_func(self) -> None:
        while self._running:
            snapshot = self.resource_pool.get_snapshot()
            total_capacity = self.resource_pool.get_total_capacity()
            utilization = self.resource_pool.get_current_utilization()
            
            metrics = ResourceMetrics(
                timestamp=time.time(),
                cpu_utilization=utilization,
                memory_utilization=utilization * 0.8,
                network_utilization=utilization * 0.6,
                active_instances=snapshot.total_instances,
                busy_instances=snapshot.busy_instances,
                overloaded_instances=snapshot.overloaded_instances
            )
            
            self.metrics_collector.record_resource_usage(metrics)
            self.resource_pool.record_usage()
            
            time.sleep(self.config.resource_monitor_interval)

    def run_scenario(self, scenario: TestScenario) -> Dict:
        print(f"Starting simulation: {scenario.name}")
        
        self._initialize_resource_pool(scenario)
        self.metrics_collector.reset()
        self._active_requests.clear()
        
        while not self._request_queue.empty():
            try:
                self._request_queue.get_nowait()
                self._request_queue.task_done()
            except Empty:
                break
        
        self._running = True
        
        self.metrics_collector.start()
        
        self._generator_thread = Thread(
            target=self._load_generator_worker,
            args=(scenario, scenario.duration_seconds)
        )
        self._generator_thread.daemon = True
        self._generator_thread.start()
        
        num_workers = 4
        self._worker_threads = []
        for _ in range(num_workers):
            worker = Thread(target=self._worker_thread_func)
            worker.daemon = True
            worker.start()
            self._worker_threads.append(worker)
        
        self._monitor_thread = Thread(target=self._monitor_thread_func)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        start_time = time.time()
        sim_duration = scenario.duration_seconds / self.config.time_scale
        
        print(f"Simulation running... (duration: {sim_duration:.1f}s)")
        
        while self._running and (time.time() - start_time) < sim_duration:
            time.sleep(0.1)
        
        print("Simulation completed, waiting for requests to finish...")
        
        self._running = False
        
        if self._generator_thread:
            self._generator_thread.join(timeout=5.0)
        
        self._request_queue.join()
        
        for worker in self._worker_threads:
            worker.join(timeout=5.0)
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        self.metrics_collector.stop()
        
        result = self.metrics_collector.get_result(
            scenario.scenario_id,
            scenario.name
        )
        
        report_files = {}
        if self.config.enable_visualization:
            print("Generating report...")
            report_files = self.report_generator.generate_full_report(result)
        
        print(f"Simulation finished: {scenario.name}")
        print(f"  Total requests: {result.overall_success_rate.total_requests}")
        print(f"  Success rate: {result.overall_success_rate.success_rate*100:.1f}%")
        print(f"  Avg response: {result.overall_response_time.avg_ms:.1f}ms")
        print(f"  P95 response: {result.overall_response_time.p95_ms:.1f}ms")
        
        return {
            "scenario": scenario,
            "result": result,
            "report_files": report_files
        }

    def run_multiple_scenarios(self, scenarios: List[TestScenario]) -> List[Dict]:
        results = []
        for scenario in scenarios:
            result = self.run_scenario(scenario)
            results.append(result)
            time.sleep(1.0)
        return results

    def reset(self) -> None:
        self._running = False
        if self.resource_pool:
            self.resource_pool.reset()
        self.metrics_collector.reset()
        self._active_requests.clear()
        while not self._request_queue.empty():
            try:
                self._request_queue.get_nowait()
                self._request_queue.task_done()
            except Empty:
                break
