# 基于状态的智能调度 Spec

## Why

当前实现中，ResourceState、QueueState、RateLimitState 主要用于监控和暴露指标，没有在调度决策中充分利用这些状态信息。通过在调度器中集成对这些状态的分析和处理，可以实现更智能、更高效的资源调度策略。

## What Changes

### 1. 新增系统状态分析器 (SystemStateAnalyzer)
- 整合 ResourceState、QueueState、RateLimitState
- 分析系统当前负载状态（低/中/高负载）
- 识别瓶颈资源（并发 Token、TPM、QPM）
- 评估场景健康度（队列积压、超时率等）

### 2. 增强调度决策逻辑
- **基于资源状态的调度**：
  - 低负载时：激进调度，优先填满资源
  - 中负载时：平衡调度，兼顾优先级和公平性
  - 高负载时：保守调度，严格按优先级，保护高优先级场景
  
- **基于队列状态的调度**：
  - 检测场景队列积压情况
  - 对积压严重的场景进行优先级临时提升（可选）
  - 避免单个场景饥饿
  
- **基于限流状态的调度**：
  - 在调度前检查 RateLimitState
  - 避免调度即将触限流的请求
  - 优先调度限流余量充足的场景

### 3. 新增调度策略配置
- 可配置的负载阈值（低/中/高负载划分）
- 可配置的调度策略参数
- 支持动态调整调度策略

### 4. 增强可观测性
- 新增调度决策日志
- 新增系统状态分析指标
- 便于调试和优化调度策略

## Impact

- 受影响的模块：`scheduler.py`, `models.py`
- 新增模块：`state_analyzer.py`
- 受影响的测试：`test_scheduler.py`

## ADDED Requirements

### Requirement: 系统状态分析器
系统 SHALL 提供 SystemStateAnalyzer 组件，整合分析 ResourceState、QueueState、RateLimitState。

#### Scenario: 状态分析
- **WHEN** 调度器进行调度决策前
- **THEN** 系统分析当前状态，包括：
  - 负载等级（低/中/高）
  - 瓶颈资源类型
  - 各场景队列积压情况
  - 各场景限流余量

### Requirement: 基于状态的智能调度
系统 SHALL 根据系统状态采用不同的调度策略。

#### Scenario: 低负载调度
- **WHEN** 系统处于低负载状态（资源使用率 < 50%）
- **THEN** 采用激进调度策略：
  - 优先填满可用资源
  - 场景可突破 max_concurrent_tokens 限制
  - 减少请求排队

#### Scenario: 中负载调度
- **WHEN** 系统处于中负载状态（50% ≤ 资源使用率 < 80%）
- **THEN** 采用平衡调度策略：
  - 按优先级 + 入队时间调度
  - 兼顾资源利用率和公平性
  - 监控队列积压情况

#### Scenario: 高负载调度
- **WHEN** 系统处于高负载状态（资源使用率 ≥ 80%）
- **THEN** 采用保守调度策略：
  - 严格按优先级调度
  - 低优先级场景排队或限流
  - 保护高优先级场景 SLA

### Requirement: 基于限流状态的预检查
系统 SHALL 在调度前检查 RateLimitState，避免调度即将触发限流的请求。

#### Scenario: 限流预检查
- **WHEN** 选择候选请求进行调度
- **THEN** 系统检查该场景的限流余量：
  - 如果 TPM 或 QPM 即将超限，跳过该请求
  - 优先调度限流余量充足的场景
