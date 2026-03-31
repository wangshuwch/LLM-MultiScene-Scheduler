from prometheus_client import (
    Gauge,
    Counter,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    def __init__(self, registry=None):
        self.registry = registry or CollectorRegistry()

        self.total_concurrent_tokens_gauge = Gauge(
            "llm_scheduler_total_concurrent_tokens",
            "Total concurrent token capacity of the LLM service",
            registry=self.registry,
        )

        self.used_concurrent_tokens_gauge = Gauge(
            "llm_scheduler_used_concurrent_tokens",
            "Currently used concurrent tokens",
            registry=self.registry,
        )

        self.available_concurrent_tokens_gauge = Gauge(
            "llm_scheduler_available_concurrent_tokens",
            "Available concurrent tokens",
            registry=self.registry,
        )

        self.scene_concurrent_usage_gauge = Gauge(
            "llm_scheduler_scene_concurrent_usage",
            "Concurrent tokens used per scene",
            ["scene_id"],
            registry=self.registry,
        )

        self.global_tpm_used_gauge = Gauge(
            "llm_scheduler_global_tpm_used",
            "Global TPM used in current window",
            registry=self.registry,
        )

        self.global_qpm_used_gauge = Gauge(
            "llm_scheduler_global_qpm_used",
            "Global QPM used in current window",
            registry=self.registry,
        )

        self.scene_tpm_used_gauge = Gauge(
            "llm_scheduler_scene_tpm_used",
            "Scene TPM used in current window",
            ["scene_id"],
            registry=self.registry,
        )

        self.scene_qpm_used_gauge = Gauge(
            "llm_scheduler_scene_qpm_used",
            "Scene QPM used in current window",
            ["scene_id"],
            registry=self.registry,
        )

        self.queue_length_gauge = Gauge(
            "llm_scheduler_queue_length",
            "Queue length per scene",
            ["scene_id"],
            registry=self.registry,
        )

        self.queue_waiting_tokens_gauge = Gauge(
            "llm_scheduler_queue_waiting_tokens",
            "Waiting tokens in queue per scene",
            ["scene_id"],
            registry=self.registry,
        )

        self.requests_total_counter = Counter(
            "llm_scheduler_requests_total",
            "Total number of requests",
            ["scene_id"],
            registry=self.registry,
        )

        self.requests_success_counter = Counter(
            "llm_scheduler_requests_success",
            "Number of successful requests",
            ["scene_id"],
            registry=self.registry,
        )

        self.requests_failed_counter = Counter(
            "llm_scheduler_requests_failed",
            "Number of failed requests",
            ["scene_id"],
            registry=self.registry,
        )

        self.requests_timeout_counter = Counter(
            "llm_scheduler_requests_timeout",
            "Number of timeout requests",
            ["scene_id"],
            registry=self.registry,
        )

        self.requests_rate_limited_counter = Counter(
            "llm_scheduler_requests_rate_limited",
            "Number of rate limited requests",
            ["scene_id"],
            registry=self.registry,
        )

        self.request_queue_time_histogram = Histogram(
            "llm_scheduler_request_queue_time_seconds",
            "Time spent in queue",
            ["scene_id"],
            registry=self.registry,
        )

        self.request_execution_time_histogram = Histogram(
            "llm_scheduler_request_execution_time_seconds",
            "Time spent executing request",
            ["scene_id"],
            registry=self.registry,
        )

    def set_total_concurrent_tokens(self, value):
        self.total_concurrent_tokens_gauge.set(value)

    def set_used_concurrent_tokens(self, value):
        self.used_concurrent_tokens_gauge.set(value)

    def set_available_concurrent_tokens(self, value):
        self.available_concurrent_tokens_gauge.set(value)

    def set_scene_concurrent_usage(self, scene_id, value):
        self.scene_concurrent_usage_gauge.labels(scene_id=scene_id).set(value)

    def set_global_tpm_used(self, value):
        self.global_tpm_used_gauge.set(value)

    def set_global_qpm_used(self, value):
        self.global_qpm_used_gauge.set(value)

    def set_scene_tpm_used(self, scene_id, value):
        self.scene_tpm_used_gauge.labels(scene_id=scene_id).set(value)

    def set_scene_qpm_used(self, scene_id, value):
        self.scene_qpm_used_gauge.labels(scene_id=scene_id).set(value)

    def set_queue_length(self, scene_id, value):
        self.queue_length_gauge.labels(scene_id=scene_id).set(value)

    def set_queue_waiting_tokens(self, scene_id, value):
        self.queue_waiting_tokens_gauge.labels(scene_id=scene_id).set(value)

    def inc_requests_total(self, scene_id):
        self.requests_total_counter.labels(scene_id=scene_id).inc()

    def inc_requests_success(self, scene_id):
        self.requests_success_counter.labels(scene_id=scene_id).inc()

    def inc_requests_failed(self, scene_id):
        self.requests_failed_counter.labels(scene_id=scene_id).inc()

    def inc_requests_timeout(self, scene_id):
        self.requests_timeout_counter.labels(scene_id=scene_id).inc()

    def inc_requests_rate_limited(self, scene_id):
        self.requests_rate_limited_counter.labels(scene_id=scene_id).inc()

    def observe_queue_time(self, scene_id, seconds):
        self.request_queue_time_histogram.labels(scene_id=scene_id).observe(seconds)

    def observe_execution_time(self, scene_id, seconds):
        self.request_execution_time_histogram.labels(scene_id=scene_id).observe(seconds)

    def generate_latest(self):
        return generate_latest(self.registry)

    @property
    def content_type(self):
        return CONTENT_TYPE_LATEST
