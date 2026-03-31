# LLM Multi-Scene Scheduler

LLM 多场景资源分配与动态调度系统

## 系统概述

本系统实现了一个高效的 LLM 多场景资源分配与动态调度机制，主要解决以下问题：

1. **资源有限性**：基于 Token (QPM/TPM) 对 LLM 服务资源进行限制
2. **多场景超卖**：支持多个场景的最大资源之和超过总容量（超卖配置）
3. **优先级调度**：当资源紧张时，按场景优先级分配资源
4. **请求排队**：资源满时，请求进入队列，按优先级+入队时间调度
5. **动态负载**：充分利用不同场景峰值时间不同的特点，提高资源利用率

## 核心特性

- ✅ 双层限流：并发 Token + 时间窗口 TPM/QPM
- ✅ 基于 Token 的精细化资源计量
- ✅ 场景级优先级与最大资源限制
- ✅ 动态资源分配与超卖支持
- ✅ 公平的排队机制（优先级 + FIFO）
- ✅ 完整的 Prometheus 监控指标
- ✅ 同步/异步请求支持
- ✅ 可扩展的架构设计

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基本使用

```python
from datetime import timedelta
from src.models import SceneConfig, LLMRequest, GlobalConfig
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator

global_config = GlobalConfig(
    total_concurrent_tokens=100000,
    global_tpm=1000000,
    global_qpm=10000,
    window_size_seconds=60,
    window_step_seconds=1,
    worker_count=5,
)

scene_configs = [
    SceneConfig(
        scene_id="chatbot",
        name="Customer Chatbot",
        priority=1,
        max_concurrent_tokens=60000,
        weight=0.5,
        timeout=timedelta(minutes=2),
    ),
    SceneConfig(
        scene_id="analytics",
        name="Data Analytics",
        priority=2,
        max_concurrent_tokens=50000,
        weight=0.3,
        timeout=timedelta(minutes=5),
    ),
]

scheduler_config = SchedulerConfig(
    global_config=global_config,
    scene_configs=scene_configs,
)

scheduler = Scheduler(
    config=scheduler_config,
    llm_client=MockLLMClient(delay=0.1),
)

scheduler.start()

req = LLMRequest(
    scene_id="chatbot",
    prompt="Hello, world!",
    max_output_token=100,
)

resp = scheduler.submit(req)
print(resp.content)

scheduler.stop()
```

### 运行示例

```bash
python examples/basic_usage.py
```

## 架构设计

### 核心组件

| 组件 | 职责 |
|-----|------|
| **Scheduler** | 核心调度器，协调各组件 |
| **ResourceManager** | 资源管理器，管理并发 Token |
| **RateLimiter** | 时间窗口限流器，TPM/QPM 限流 |
| **QueueManager** | 队列管理器，管理各场景请求队列 |
| **TokenEstimator** | Token 估算器 |
| **MetricsCollector** | 监控指标采集器 |

### 目录结构

```
LLM-MultiScene-Scheduler/
├── src/
│   ├── __init__.py
│   ├── models.py          # 数据模型和错误定义
│   ├── scheduler.py       # 核心调度器
│   ├── resource_manager.py # 资源管理器（并发 Token）
│   ├── rate_limiter.py   # 时间窗口限流器（TPM/QPM）
│   ├── queue_manager.py  # 队列管理器
│   ├── token_estimator.py # Token 估算器
│   └── metrics.py        # Prometheus 监控指标
├── tests/
│   ├── unit/
│   ├── integration/
│   └── load/
├── examples/
│   └── basic_usage.py
├── configs/
│   └── scheduler.yaml
├── design/
│   ├── spec.md
│   ├── tasks.md
│   └── checklist.md
├── requirements.txt
└── README.md
```

## 调度策略

### 资源分配策略

1. **总需求 ≤ 总容量**：所有场景可以自由使用资源，不受场景 max_tokens 限制
2. **总需求 &gt; 总容量**：
   - 按优先级分组，高优先级优先保障
   - 同时受场景 max_tokens 限制

### 队列调度策略

调度优先级：
1. 场景优先级（Priority，数字越小优先级越高）
2. 入队时间（EnqueueTime，FIFO）

## 监控指标

系统内置完整的 Prometheus 监控指标：

| 指标 | 类型 | 描述 |
|-----|------|------|
| `llm_scheduler_total_concurrent_tokens` | Gauge | 总并发 Token 容量 |
| `llm_scheduler_used_concurrent_tokens` | Gauge | 已使用并发 Token |
| `llm_scheduler_available_concurrent_tokens` | Gauge | 可用并发 Token |
| `llm_scheduler_scene_concurrent_usage` | Gauge | 各场景并发 Token 使用量 |
| `llm_scheduler_global_tpm_used` | Gauge | 全局 TPM 使用量 |
| `llm_scheduler_global_qpm_used` | Gauge | 全局 QPM 使用量 |
| `llm_scheduler_scene_tpm_used` | Gauge | 各场景 TPM 使用量 |
| `llm_scheduler_scene_qpm_used` | Gauge | 各场景 QPM 使用量 |
| `llm_scheduler_queue_length` | Gauge | 队列长度 |
| `llm_scheduler_queue_waiting_tokens` | Gauge | 队列等待 Token 总量 |
| `llm_scheduler_requests_total` | Counter | 请求总数 |
| `llm_scheduler_requests_success` | Counter | 成功请求数 |
| `llm_scheduler_requests_failed` | Counter | 失败请求数 |
| `llm_scheduler_requests_timeout` | Counter | 超时请求数 |
| `llm_scheduler_requests_rate_limited` | Counter | 被限流请求数 |
| `llm_scheduler_request_queue_time_seconds` | Histogram | 请求排队时间 |
| `llm_scheduler_request_execution_time_seconds` | Histogram | 请求执行时间 |

## 配置说明

参考 [configs/scheduler.yaml](configs/scheduler.yaml)

## 扩展能力

### 自定义 LLM Client

继承 `LLMClient` 类并实现 `call` 方法：

```python
from src.scheduler import LLMClient
from src.models import LLMResponse

class MyLLMClient(LLMClient):
    def call(self, prompt: str, max_output_token: int) -&gt; LLMResponse:
        pass
```

### 自定义 Token Estimator

继承 `TokenEstimator` 类：

```python
from src.token_estimator import TokenEstimator

class MyEstimator(TokenEstimator):
    def estimate(self, prompt: str, max_output_token: int) -&gt; int:
        pass
```

## 许可证

MIT License
