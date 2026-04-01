# LLM Multi-Scene Scheduler

LLM 多场景资源分配与动态调度系统

## 系统概述

本系统实现了一个高效的 LLM 多场景资源分配与动态调度机制，主要解决以下问题：

1. **资源有限性**：基于 Token (QPM/TPM) 对 LLM 服务资源进行限制
2. **多场景超卖**：支持多个场景的最大资源之和超过总容量（超卖配置）
3. **优先级调度**：当资源紧张时，按场景优先级分配资源
4. **请求排队**：资源满时，请求进入队列，按优先级+入队时间调度
5. **动态负载**：充分利用不同场景峰值时间不同的特点，提高资源利用率
6. **基于状态的智能调度**：v0.2 新增，整合 ResourceState、QueueState、RateLimitState 进行智能调度决策

## 核心特性

- ✅ 双层限流：并发 Token + 时间窗口 TPM/QPM
- ✅ 基于 Token 的精细化资源计量
- ✅ 场景级优先级与最大资源限制
- ✅ 动态资源分配与超卖支持
- ✅ 公平的排队机制（优先级 + FIFO）
- ✅ 完整的 Prometheus 监控指标
- ✅ 同步/异步请求支持
- ✅ 可扩展的架构设计
- ✅ **v0.2 新增**：基于状态的智能调度器 (SystemStateAnalyzer)
- ✅ **v0.2 新增**：限流预检查，避免调度即将触限流的请求
- ✅ **v0.2 新增**：可配置的调度策略

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

依赖包括：
- prometheus-client - 监控指标
- tiktoken - Token 估算（可选）
- pyyaml - 配置管理
- matplotlib - 可视化（v0.2 新增）
- seaborn - 可视化（v0.2 新增）
- numpy - 数值计算（v0.2 新增）

### 基本使用

```python
from datetime import timedelta
from src.models import SceneConfig, LLMRequest, GlobalConfig
from src.scheduler import Scheduler, SchedulerConfig, MockLLMClient
from src.token_estimator import SimpleEstimator
from src.state_analyzer import SchedulingStrategyConfig

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

# 可选：自定义调度策略配置
strategy_config = SchedulingStrategyConfig(
    low_load_threshold=0.4,      # 低负载阈值（默认 0.5）
    medium_load_threshold=0.75,   # 中负载阈值（默认 0.8）
    tpm_warning_threshold=0.85,    # TPM 告警阈值（默认 0.9）
    qpm_warning_threshold=0.85,    # QPM 告警阈值（默认 0.9）
)

scheduler = Scheduler(
    config=scheduler_config,
    llm_client=MockLLMClient(delay=0.1),
    scheduling_strategy_config=strategy_config,
)

scheduler.start()

req = LLMRequest(
    scene_id="chatbot",
    prompt="Hello, world!",
    max_output_token=100,
)

resp = scheduler.submit(req)
print(resp.content)

# 获取系统状态分析结果
system_state = scheduler.get_last_system_state()
print("Load level:", system_state.load_level)
print("Bottleneck resource:", system_state.bottleneck_resource)

scheduler.stop()
```

### 运行示例

```bash
python examples/basic_usage.py
```

### v0.2 新增：运行模拟测试

项目包含完整的模拟测试系统，用于验证调度器在不同负载条件下的性能表现：

```bash
# 验证组件
python tests/simulation/verify_components.py

# 快速测试
python tests/simulation/quick_test.py

# 运行单个场景
python tests/simulation/main.py single scenario_c -t 100

# 运行所有场景
python tests/simulation/main.py all -t 100
```

详细说明请参考 [tests/simulation/README.md](tests/simulation/README.md)

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
| **SystemStateAnalyzer** | v0.2 新增，系统状态分析器 |

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
│   ├── metrics.py        # Prometheus 监控指标
│   └── state_analyzer.py # v0.2 新增，系统状态分析器
├── tests/
│   ├── unit/
│   │   ├── test_scheduler.py              # 基础单元测试
│   │   └── test_scheduler_comprehensive.py # v0.2 新增，完整测试用例
│   └── simulation/               # v0.2 新增，模拟测试系统
│       ├── README.md
│       ├── resource_pool.py     # 模拟 LLM 服务资源池
│       ├── load_generator.py    # 多场景负载生成器
│       ├── scenarios.py         # 测试场景定义
│       ├── monitoring.py        # 监控和评估模块
│       ├── visualization.py     # 可视化报告生成器
│       ├── orchestrator.py      # 主模拟协调器
│       ├── main.py              # 命令行入口
│       ├── example_usage.py      # 使用示例
│       └── verify_components.py  # 组件验证脚本
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
2. **总需求 > 总容量**：
   - 按优先级分组，高优先级优先保障
   - 同时受场景 max_tokens 限制

### 队列调度策略

调度优先级：
1. 场景优先级（Priority，数字越小优先级越高）
2. 入队时间（EnqueueTime，FIFO）

### v0.2 新增：基于状态的智能调度

系统会在调度前分析当前状态，包括：
- **负载等级** (LoadLevel)：低/中/高负载
- **瓶颈资源** (BottleneckResource)：并发 Token / TPM / QPM / 无
- **场景健康度** (SceneHealth)：各场景队列积压、限流余量等

智能调度特性：
- 低负载时：激进调度，优先填满资源
- 中负载时：平衡调度，兼顾优先级和公平性
- 高负载时：保守调度，严格按优先级，保护高优先级场景
- 限流预检查：避免调度即将触发限流的请求

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

## 测试

### 单元测试

```bash
# 运行基础单元测试
python -m pytest tests/unit/test_scheduler.py -v

# 运行完整测试用例
python -m pytest tests/unit/test_scheduler_comprehensive.py -v
```

### 模拟测试

项目包含完整的模拟测试系统，用于验证调度器在不同负载条件下的性能表现。

**4 个预定义测试场景**：
- Scenario A - Daytime Peak (9:00-18:00)：日间峰值，正弦波流量模式
- Scenario B - Nighttime Peak (23:00-02:00)：夜间峰值，指数增长流量模式
- Scenario C - Extreme Burst：极端突发，测试系统弹性
- Scenario D - Mixed Requests：混合请求，长尾 + 小请求混合

**运行测试**：
```bash
# 验证组件
python tests/simulation/verify_components.py

# 快速测试
python tests/simulation/quick_test.py

# 列出所有可用场景
python tests/simulation/main.py list

# 运行单个场景（使用 100x 时间加速）
python tests/simulation/main.py single scenario_c -t 100

# 运行所有场景
python tests/simulation/main.py all -t 100
```

详细说明请参考 [tests/simulation/README.md](tests/simulation/README.md)

## 扩展能力

### 自定义 LLM Client

继承 `LLMClient` 类并实现 `call` 方法：

```python
from src.scheduler import LLMClient
from src.models import LLMResponse

class MyLLMClient(LLMClient):
    def call(self, prompt: str, max_output_token: int) -> LLMResponse:
        pass
```

### 自定义 Token Estimator

继承 `TokenEstimator` 类：

```python
from src.token_estimator import TokenEstimator

class MyEstimator(TokenEstimator):
    def estimate(self, prompt: str, max_output_token: int) -> int:
        pass
```

### v0.2 新增：自定义调度策略

使用 `SchedulingStrategyConfig` 自定义调度策略：

```python
from src.state_analyzer import SchedulingStrategyConfig

strategy_config = SchedulingStrategyConfig(
    low_load_threshold=0.4,      # 低负载阈值
    medium_load_threshold=0.75,   # 中负载阈值
    tpm_warning_threshold=0.85,    # TPM 告警阈值
    qpm_warning_threshold=0.85,    # QPM 告警阈值
)

# 动态更新调度策略
scheduler.update_scheduling_strategy_config(strategy_config)
```

## 版本历史

### v0.2
- 新增基于状态的智能调度器 (SystemStateAnalyzer)
- 新增限流预检查功能
- 优化资源分配策略
- 优化队列调度流程
- **新增完整模拟测试系统** (tests/simulation/)
  - 模拟 LLM 服务资源池
  - 多场景负载生成器（多种流量模式和 token 分布）
  - 4 个预定义测试场景
  - 完整监控和评估模块
  - 可视化报告生成器（matplotlib/seaborn）
  - HTML 综合报告
  - 命令行接口
- **新增完整测试用例** (tests/unit/test_scheduler_comprehensive.py)
- **新增可视化依赖** (matplotlib, seaborn, numpy)

### v0.1
- 初始版本
- 核心调度功能
- 双层限流机制
- 优先级调度
- 完整监控指标

## 许可证

MIT License
