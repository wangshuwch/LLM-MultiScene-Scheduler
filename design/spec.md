# LLM 多场景资源分配系统 - 技术方案文档

## 1. 概述

### 1.1 项目背景

当前 LLM 服务面临以下挑战：
- **资源有限**：基于 QPM (Queries Per Minute) 和 TPM (Tokens Per Minute) 对资源有限制
- **多场景需求**：服务于多个业务场景，各场景资源需求之和远超可用资源
- **负载不均**：不同场景的峰值时间不同，存在资源浪费
- **服务质量保障**：需要确保高优先级场景的服务质量

### 1.2 核心目标

1. **资源高效利用**：充分利用 LLM 资源，提高利用率
2. **超卖支持**：支持场景最大资源之和超过总容量
3. **优先级保障**：高优先级场景在资源紧张时优先获得资源
4. **公平排队**：按优先级+入队时间公平调度
5. **TPM/QPM 限流**：基于时间窗口的精细化限流
6. **可观测性**：完整的监控指标

---

## 2. 核心假设（基于工业实践）

基于常见工业实践，我们做出以下合理假设：

| 假设项 | 假设内容 | 说明 |
|--------|----------|------|
| **资源计量** | 双层限流：并发 Token + 时间窗口 TPM/QPM | 同时限制并发执行的 Token 量和每分钟的 Token/请求数 |
| **优先级规则** | 数字越小优先级越高（P1 > P2 > P3） | 同优先级场景按权重比例分配资源 |
| **超卖策略** | 资源充裕时场景可突破 max_tokens 限制 | 资源紧张时受 max_tokens 限制 |
| **调度策略** | 按需分配（FIFO + 优先级） | 每次选取一个请求，简单高效 |
| **流式输出** | 暂不支持，仅支持非流式输出 | 简化实现，后续可扩展 |
| **Token 计量** | 基于预估值分配，完成后不调整 | 使用 `len(tiktoken(prompt)) + max_output_token` |
| **队列设计** | 每个场景独立队列 | 支持场景级队列长度限制和超时 |
| **优先级粒度** | 场景级优先级 | 同一场景的所有请求优先级相同 |
| **限流算法** | 滑动窗口 + 令牌桶混合 | 滑动窗口精确计数，令牌桶平滑流量 |

---

## 3. 系统架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (可选)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   REST API   │  │  gRPC API    │  │  WebSocket   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼───────────────────┼───────────────────┼──────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Request Coordinator                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Scene Router│  │  Rate Limiter│  │  Validator   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  Scene Queue 1 │ │  Scene Queue 2 │ │  Scene Queue N │
│  (Priority P1) │ │  (Priority P2) │ │  (Priority Pn) │
└────────────────┘ └────────────────┘ └────────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Scheduler Engine                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Resource Manager (资源管理器)                      │  │
│  │  - 并发 Token 管理                                        │  │
│  │  - 场景 max_tokens 检查                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Rate Limiter (时间窗口限流器)                      │  │
│  │  - 滑动窗口 TPM/QPM 计数                                  │  │
│  │  - 令牌桶平滑流量                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Queue Dispatcher (队列分发器)                      │  │
│  │  - 优先级排序 + FIFO                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  Worker Pool 1 │ │  Worker Pool 2 │ │  Worker Pool N │
│  (LLM Calls)   │ │  (LLM Calls)   │ │  (LLM Calls)   │
└────────────────┘ └────────────────┘ └────────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Metrics &amp; Monitoring                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Prometheus  │  │   Grafana    │  │ AlertManager │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件职责

| 组件 | 模块 | 职责 |
|------|------|------|
| **Request Coordinator** | 请求协调器 | 场景路由、请求验证、限流检查 |
| **Scene Queue** | 场景队列 | 每个场景独立的请求队列 |
| **Resource Manager** | 资源管理器 | 并发 Token 分配与释放、场景 max_tokens 检查 |
| **Rate Limiter** | 时间窗口限流器 | TPM/QPM 滑动窗口限流、令牌桶平滑 |
| **Queue Dispatcher** | 队列分发器 | 从队列中选取请求执行（优先级 + FIFO） |
| **Worker Pool** | 工作池 | 执行实际的 LLM 调用 |
| **Token Estimator** | Token 估算器 | 估算请求 Token 消耗 |
| **Metrics** | 监控指标 | Prometheus 指标采集 |

---

## 4. 核心数据结构设计

### 4.1 全局配置 (GlobalConfig)

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_concurrent_tokens` | Int | 并发 Token 总容量 |
| `global_tpm` | Int | 全局 TPM 限制（每分钟 Token 数） |
| `global_qpm` | Int | 全局 QPM 限制（每分钟请求数） |
| `window_size_seconds` | Int | 时间窗口大小（默认 60 秒） |
| `window_step_seconds` | Int | 滑动步长（默认 1 秒） |
| `worker_count` | Int | Worker 数量 |

### 4.2 场景配置 (SceneConfig)

| 字段 | 类型 | 说明 |
|------|------|------|
| `scene_id` | String | 场景唯一标识 |
| `name` | String | 场景名称 |
| `priority` | Int | 优先级（数字越小优先级越高） |
| `max_concurrent_tokens` | Int | 最大并发 Token 限制（超卖配置） |
| `weight` | Float | 权重（0-1，同优先级资源分配比例） |
| `scene_tpm` | Int | 场景 TPM 限制 |
| `scene_qpm` | Int | 场景 QPM 限制 |
| `is_enabled` | Boolean | 是否启用 |
| `queue_size` | Int | 队列最大长度 |
| `timeout` | Duration | 请求超时时间 |

### 4.3 请求结构 (LLMRequest)

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | String | 请求唯一 ID |
| `scene_id` | String | 所属场景 ID |
| `prompt` | String | 输入提示词 |
| `max_output_token` | Int | 最大输出 Token 数 |
| `token_estimate` | Int | 预估 Token 消耗 |
| `enqueue_time` | DateTime | 入队时间 |
| `deadline` | DateTime | 超时截止时间 |
| `callback` | Function | 异步回调函数 |

### 4.4 响应结构 (LLMResponse)

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | String | 请求 ID |
| `scene_id` | String | 场景 ID |
| `content` | String | LLM 响应内容 |
| `tokens_used` | Int | 实际使用 Token 数 |
| `duration` | Duration | 执行耗时 |

### 4.5 资源状态 (ResourceState)

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_concurrent_tokens` | Int | 总并发 Token 容量 |
| `used_concurrent_tokens` | Int | 已使用并发 Token |
| `available_concurrent_tokens` | Int | 可用并发 Token |
| `scene_concurrent_usage` | Map&lt;String, Int&gt; | 各场景并发 Token 使用量 |

### 4.6 限流状态 (RateLimitState)

| 字段 | 类型 | 说明 |
|------|------|------|
| `global_tpm_used` | Int | 当前窗口全局已用 TPM |
| `global_qpm_used` | Int | 当前窗口全局已用 QPM |
| `scene_tpm_used` | Map&lt;String, Int&gt; | 各场景已用 TPM |
| `scene_qpm_used` | Map&lt;String, Int&gt; | 各场景已用 QPM |
| `window_start` | DateTime | 当前窗口开始时间 |
| `window_end` | DateTime | 当前窗口结束时间 |

---

## 5. 核心算法设计

### 5.1 资源分配策略

#### 场景 A：资源充裕（总需求 ≤ 总容量）
- **策略**：所有场景自由使用资源
- **规则**：不受场景 `max_concurrent_tokens` 限制，按实际需求分配

#### 场景 B：资源紧张（总需求 &gt; 总容量）
- **策略**：按优先级+场景 max_tokens 限制
- **规则**：
  1. 高优先级场景优先
  2. 同时受场景 `max_concurrent_tokens` 限制

**资源获取伪代码**：

```python
function try_acquire(scene_id, tokens):
    // 1. 检查全局并发 Token
    if used_concurrent_tokens + tokens &gt; total_concurrent_tokens:
        return false

    // 2. 检查场景 max_concurrent_tokens（仅在资源紧张时生效）
    total_demand = calculate_total_demand()
    if total_demand &gt; total_concurrent_tokens:
        if scene_usage[scene_id] + tokens &gt; scene_max_tokens[scene_id]:
            return false

    // 3. 分配资源
    used_concurrent_tokens += tokens
    scene_usage[scene_id] += tokens
    return true
```

### 5.2 队列调度策略

**调度优先级排序**：
1. **一级优先级**：场景 `priority`（数字越小优先级越高）
2. **二级优先级**：入队时间 `enqueue_time`（FIFO）

**选择算法**：

```python
function select_next_request(queues):
    best_scene = null
    best_priority = MAX_INT
    best_enqueue_time = MAX_DATETIME

    for scene_id, queue in queues:
        if queue is empty:
            continue

        front = queue.front()
        cfg = get_scene_config(scene_id)

        if cfg.priority &lt; best_priority:
            best_priority = cfg.priority
            best_scene = scene_id
            best_enqueue_time = front.enqueue_time
        elif cfg.priority == best_priority:
            if front.enqueue_time &lt; best_enqueue_time:
                best_scene = scene_id
                best_enqueue_time = front.enqueue_time

    if best_scene is not null:
        return queues[best_scene].dequeue()

    return null
```

### 5.3 TPM/QPM 滑动窗口限流

#### 5.3.1 滑动窗口实现

**数据结构**：
- 使用环形数组存储每个时间槽的计数
- 每个时间槽 = 1 秒
- 保留最近 60 个时间槽

**算法伪代码**：

```python
class SlidingWindowRateLimiter:
    function __init__(global_tpm, global_qpm, window_size=60):
        this.global_tpm = global_tpm
        this.global_qpm = global_qpm
        this.window_size = window_size

        // 全局计数
        this.global_token_slots = new Array(window_size)
        this.global_query_slots = new Array(window_size)

        // 场景计数
        this.scene_token_slots = {}
        this.scene_query_slots = {}

        this.current_slot_index = 0
        this.last_update_time = now()

    function try_acquire(scene_id, tokens):
        this.advance_window()

        // 计算当前窗口计数
        global_tokens = sum(this.global_token_slots)
        global_queries = sum(this.global_query_slots)

        // 检查全局限流
        if global_tokens + tokens &gt; this.global_tpm:
            return false
        if global_queries + 1 &gt; this.global_qpm:
            return false

        // 检查场景限流
        if scene_id in this.scene_token_slots:
            scene_tokens = sum(this.scene_token_slots[scene_id])
            scene_queries = sum(this.scene_query_slots[scene_id])

            scene_config = get_scene_config(scene_id)
            if scene_tokens + tokens &gt; scene_config.scene_tpm:
                return false
            if scene_queries + 1 &gt; scene_config.scene_qpm:
                return false

        // 预占槽位（临时计数）
        this.global_token_slots[this.current_slot_index] += tokens
        this.global_query_slots[this.current_slot_index] += 1

        if scene_id not in this.scene_token_slots:
            this.scene_token_slots[scene_id] = new Array(window_size)
            this.scene_query_slots[scene_id] = new Array(window_size)
        this.scene_token_slots[scene_id][this.current_slot_index] += tokens
        this.scene_query_slots[scene_id][this.current_slot_index] += 1

        return true

    function advance_window():
        now = now()
        seconds_passed = now - this.last_update_time

        for i in 0 to seconds_passed - 1:
            slot_index = (this.current_slot_index + 1) % this.window_size
            this.global_token_slots[slot_index] = 0
            this.global_query_slots[slot_index] = 0

            for scene_id in this.scene_token_slots:
                this.scene_token_slots[scene_id][slot_index] = 0
                this.scene_query_slots[scene_id][slot_index] = 0

            this.current_slot_index = slot_index

        this.last_update_time = now
```

#### 5.3.2 令牌桶（用于平滑流量）

```python
class TokenBucket:
    function __init__(capacity, refill_rate):
        this.capacity = capacity
        this.refill_rate = refill_rate
        this.tokens = capacity * 0.5  // 初始 50%
        this.last_refill_time = now()

    function try_consume(tokens):
        this.refill()
        if this.tokens &gt;= tokens:
            this.tokens -= tokens
            return true
        return false

    function refill():
        now = now()
        seconds_passed = now - this.last_refill_time
        this.tokens = min(
            this.capacity,
            this.tokens + seconds_passed * this.refill_rate
        )
        this.last_refill_time = now
```

---

## 6. 超卖设计详解

### 6.1 什么是资源超卖

**超卖定义**：所有场景的 `max_concurrent_tokens` 之和 &gt; 系统总容量 `total_concurrent_tokens`

**超卖意义**：
- 利用不同场景峰值时间不同的特点
- 提高资源整体利用率
- 在保障高优先级场景的前提下，允许低优先级场景"借"用资源

### 6.2 超卖配置示例

| 场景 | 优先级 | max_concurrent_tokens | 权重 |
|-----|--------|---------------------|------|
| Chatbot (客服) | 1 | 60,000 | 0.5 |
| Analytics (分析) | 2 | 50,000 | 0.3 |
| Background (后台) | 3 | 40,000 | 0.2 |
| **合计** | - | **150,000** | 1.0 |

**系统总容量**：100,000 tokens

**超卖比例**：150,000 / 100,000 = **1.5 倍**

### 6.3 超卖场景下的调度策略

#### 阶段 1：低负载（所有场景需求之和 ≤ 总容量）
- **策略**：自由使用，不受 `max_concurrent_tokens` 限制
- **效果**：资源充分利用，无排队

#### 阶段 2：中负载（部分场景活跃）
- **策略**：活跃场景可使用超过其"公平份额"的资源
- **效果**：闲置场景的资源被活跃场景"借"用

#### 阶段 3：高负载（所有场景需求之和 &gt; 总容量）
- **策略**：
  1. 高优先级场景优先保障（接近或达到其 `max_concurrent_tokens`）
  2. 中优先级场景按权重分配
  3. 低优先级场景排队等待或限流
- **效果**：高优先级 SLA 不受影响

### 6.4 超卖的风险控制

| 风险 | 控制措施 |
|-----|---------|
| 低优先级场景饥饿 | 设置最低保障比例（如 10%） |
| 突发流量冲击 | 队列限流 + 快速失败 |
| 配置错误 | 配置校验（超卖比例建议 &lt; 2x） |
| 资源耗尽 | 监控告警 + 自动降级 |

---

## 7. 请求生命周期

```
    [提交]
       │
       ▼
┌──────────────┐
│  限流检查    │ ──► [限流拒绝]
│  (TPM/QPM)   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  队列等待    │ ──► [超时/取消]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  资源获取    │ ──► [资源不足，返回等待]
│  (并发Token) │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  执行中      │ ──► [执行失败]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  完成        │
└──────────────┘
```

---

## 8. 监控指标设计

### 8.1 核心指标列表

| 指标名称 | 类型 | 标签 | 描述 |
|---------|------|------|------|
| `llm_scheduler_total_concurrent_tokens` | Gauge | - | 总并发 Token 容量 |
| `llm_scheduler_used_concurrent_tokens` | Gauge | - | 已使用并发 Token |
| `llm_scheduler_available_concurrent_tokens` | Gauge | - | 可用并发 Token |
| `llm_scheduler_scene_concurrent_usage` | Gauge | `scene_id` | 各场景并发 Token 使用量 |
| `llm_scheduler_global_tpm_used` | Gauge | - | 全局 TPM 使用量 |
| `llm_scheduler_global_qpm_used` | Gauge | - | 全局 QPM 使用量 |
| `llm_scheduler_scene_tpm_used` | Gauge | `scene_id` | 各场景 TPM 使用量 |
| `llm_scheduler_scene_qpm_used` | Gauge | `scene_id` | 各场景 QPM 使用量 |
| `llm_scheduler_queue_length` | Gauge | `scene_id` | 队列长度 |
| `llm_scheduler_queue_waiting_tokens` | Gauge | `scene_id` | 队列等待 Token 总量 |
| `llm_scheduler_requests_total` | Counter | `scene_id` | 请求总数 |
| `llm_scheduler_requests_success` | Counter | `scene_id` | 成功请求数 |
| `llm_scheduler_requests_failed` | Counter | `scene_id` | 失败请求数 |
| `llm_scheduler_requests_timeout` | Counter | `scene_id` | 超时请求数 |
| `llm_scheduler_requests_rate_limited` | Counter | `scene_id` | 被限流请求数 |
| `llm_scheduler_request_queue_time_seconds` | Histogram | `scene_id` | 请求排队时间分布 |
| `llm_scheduler_request_execution_time_seconds` | Histogram | `scene_id` | 请求执行时间分布 |

### 8.2 告警规则

| 告警名称 | 触发条件 | 严重程度 |
|---------|---------|---------|
| 队列过长 | `llm_scheduler_queue_length{scene_id="xxx"} &gt; 100` | WARNING |
| 资源紧张 | `llm_scheduler_available_concurrent_tokens &lt; total_concurrent_tokens * 0.1` | WARNING |
| 超时率高 | `rate(llm_scheduler_requests_timeout[5m]) / rate(llm_scheduler_requests_total[5m]) &gt; 0.05` | CRITICAL |
| 限流率高 | `rate(llm_scheduler_requests_rate_limited[5m]) / rate(llm_scheduler_requests_total[5m]) &gt; 0.1` | WARNING |
| 排队时间长 | `histogram_quantile(0.95, sum(rate(llm_scheduler_request_queue_time_seconds_bucket[5m])) by (le)) &gt; 30` | WARNING |

---

## 9. 异常处理与降级策略

### 9.1 错误类型定义

| 错误类型 | 触发场景 | 处理策略 |
|---------|---------|---------|
| `SceneNotFoundError` | 场景 ID 不存在 | 拒绝请求，返回 404 |
| `SceneDisabledError` | 场景已禁用 | 拒绝请求，返回 503 |
| `QueueFullError` | 队列已满 | 快速失败，建议客户端重试 |
| `RequestTimeoutError` | 请求超时 | 清理队列，回调通知 |
| `SchedulerStoppedError` | 调度器已停止 | 拒绝请求 |
| `RateLimitError` | 触发 TPM/QPM 限流 | 快速失败，建议客户端重试 |
| `ResourceExhaustedError` | 并发 Token 耗尽 | 请求排队等待 |

### 9.2 降级策略

| 场景 | 降级策略 |
|------|---------|
| **队列满** | 返回 `QueueFullError`，建议指数退避重试 |
| **TPM/QPM 限流** | 返回 `RateLimitError`，建议指数退避重试 |
| **并发 Token 耗尽** | 请求进入队列排队，不立即失败 |
| **高优先级场景过载** | 低优先级场景限流，保障高优先级 |
| **系统过载** | 触发全局限流，快速失败 |

---

## 10. 配置示例

```yaml
# 全局配置
global:
  total_concurrent_tokens: 100000
  global_tpm: 1000000
  global_qpm: 10000
  window_size_seconds: 60
  window_step_seconds: 1
  worker_count: 10

# 场景配置
scenes:
  - scene_id: chatbot
    name: Customer Chatbot
    priority: 1
    max_concurrent_tokens: 60000
    weight: 0.5
    scene_tpm: 500000
    scene_qpm: 5000
    is_enabled: true
    queue_size: 1000
    timeout_seconds: 120

  - scene_id: analytics
    name: Data Analytics
    priority: 2
    max_concurrent_tokens: 50000
    weight: 0.3
    scene_tpm: 300000
    scene_qpm: 3000
    is_enabled: true
    queue_size: 500
    timeout_seconds: 300

  - scene_id: background
    name: Background Jobs
    priority: 3
    max_concurrent_tokens: 40000
    weight: 0.2
    scene_tpm: 200000
    scene_qpm: 2000
    is_enabled: true
    queue_size: 200
    timeout_seconds: 600
```

---

## 11. 扩展性设计

### 11.1 可扩展点

| 扩展点 | 接口 | 说明 |
|-------|------|------|
| **调度算法** | `QueueDispatcher` | 自定义队列调度策略 |
| **限流策略** | `RateLimiter` | 自定义限流规则 |
| **Token 估算** | `TokenEstimator` | 自定义 Token 估算逻辑 |
| **LLM 客户端** | `LLMClient` | 对接不同 LLM 提供商 |
| **资源管理** | `ResourceManager` | 自定义资源管理策略 |

### 11.2 未来特性扩展

- [ ] 流式输出支持
- [ ] 请求级优先级细分
- [ ] 动态权重调整（基于历史负载）
- [ ] 预测性调度（基于负载预测）
- [ ] 多 LLM 提供商支持与负载均衡
- [ ] 灰度发布支持
- [ ] 请求熔断与降级
- [ ] 分布式部署支持

---

## 12. 测试方案

### 12.1 测试目标

1. **功能验证**：验证调度逻辑正确性
2. **性能测试**：验证系统吞吐量和延迟
3. **压力测试**：验证系统在高负载下的稳定性
4. **场景模拟**：模拟真实业务场景的负载特征

### 12.2 核心测试用例

#### 测试用例 1：基础功能验证
- 同步请求提交
- 异步请求提交
- 场景不存在
- 场景禁用

#### 测试用例 2：资源分配策略验证
- 总需求 ≤ 总容量：所有场景自由使用
- 总需求 &gt; 总容量：按优先级分配
- 超卖场景验证

#### 测试用例 3：队列调度策略验证
- 优先级调度
- 同优先级 FIFO

#### 测试用例 4：TPM/QPM 限流验证
- 全局限流
- 场景级限流
- 滑动窗口正确性

#### 测试用例 5：超时处理验证

#### 测试用例 6：性能测试
- 吞吐量
- P99 延迟
- 队列积压

---

## 13. 目录结构

```
LLM-MultiScene-Scheduler/
├── src/                          # 核心代码
│   ├── __init__.py
│   ├── models.py                 # 数据模型和错误定义
│   ├── scheduler.py              # 核心调度器
│   ├── resource_manager.py       # 资源管理器（并发 Token）
│   ├── rate_limiter.py           # 时间窗口限流器（TPM/QPM）
│   ├── queue_manager.py          # 队列管理器
│   ├── token_estimator.py        # Token 估算器
│   └── metrics.py                # Prometheus 监控指标
├── tests/                        # 测试
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── load/                     # 压力测试
├── examples/                     # 示例
│   └── basic_usage.py
├── configs/                      # 配置
│   └── scheduler.yaml
├── design/                       # 设计文档
│   ├── spec.md                   # 技术方案文档
│   ├── tasks.md                  # 任务清单
│   └── checklist.md              # 检查清单
├── requirements.txt
├── setup.py
└── README.md
```
