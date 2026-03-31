# LLM 多场景资源分配系统 - 任务清单

## 阶段 1：项目初始化与配置

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T1.1 | 清空现有代码库 | High | 0.5h | - | pending |
| T1.2 | 创建项目目录结构 | High | 0.5h | T1.1 | pending |
| T1.3 | 配置 requirements.txt | High | 0.5h | T1.2 | pending |
| T1.4 | 创建配置文件示例 | Medium | 0.5h | T1.2 | pending |

## 阶段 2：核心数据模型

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T2.1 | 实现数据模型 (models.py) | High | 2h | T1.3 | pending |
| T2.2 | 实现错误类型定义 | High | 1h | T2.1 | pending |
| T2.3 | 编写模型单元测试 | Medium | 1h | T2.2 | pending |

## 阶段 3：Token 估算器

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T3.1 | 实现 TokenEstimator 抽象接口 | High | 0.5h | T2.1 | pending |
| T3.2 | 实现 SimpleEstimator | High | 0.5h | T3.1 | pending |
| T3.3 | 集成 tiktoken 实现 TiktokenEstimator | Medium | 1h | T3.1 | pending |
| T3.4 | 编写 Token 估算器单元测试 | Medium | 1h | T3.2 | pending |

## 阶段 4：资源管理器（并发 Token）

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T4.1 | 实现 ResourceManager 核心逻辑 | High | 2h | T2.1 | pending |
| T4.2 | 实现 try_acquire 方法（含超卖逻辑） | High | 2h | T4.1 | pending |
| T4.3 | 实现 release 方法 | High | 1h | T4.1 | pending |
| T4.4 | 实现 get_state 方法 | Medium | 0.5h | T4.1 | pending |
| T4.5 | 编写 ResourceManager 单元测试 | High | 2h | T4.4 | pending |

## 阶段 5：时间窗口限流器（TPM/QPM）

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T5.1 | 实现滑动窗口数据结构 | High | 2h | T2.1 | pending |
| T5.2 | 实现 SlidingWindowRateLimiter | High | 3h | T5.1 | pending |
| T5.3 | 实现 TokenBucket（可选，用于平滑） | Medium | 2h | T5.2 | pending |
| T5.4 | 实现 get_rate_limit_state 方法 | Medium | 1h | T5.2 | pending |
| T5.5 | 编写 RateLimiter 单元测试 | High | 3h | T5.4 | pending |

## 阶段 6：队列管理器

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T6.1 | 实现 SceneQueue 数据结构 | High | 1h | T2.1 | pending |
| T6.2 | 实现 QueueManager 核心逻辑 | High | 2h | T6.1 | pending |
| T6.3 | 实现 enqueue 方法（含队列满检查） | High | 1h | T6.2 | pending |
| T6.4 | 实现 dequeue 方法（优先级 + FIFO） | High | 2h | T6.2 | pending |
| T6.5 | 实现 cleanup_expired 方法 | Medium | 1h | T6.2 | pending |
| T6.6 | 编写 QueueManager 单元测试 | High | 2h | T6.5 | pending |

## 阶段 7：监控指标

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T7.1 | 实现 MetricsCollector | High | 2h | T2.1 | pending |
| T7.2 | 定义所有 Prometheus 指标 | High | 2h | T7.1 | pending |
| T7.3 | 实现指标更新方法 | Medium | 1h | T7.2 | pending |
| T7.4 | 编写 Metrics 单元测试 | Medium | 1h | T7.3 | pending |

## 阶段 8：核心调度器

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T8.1 | 实现 SchedulerConfig | High | 1h | T2.1 | pending |
| T8.2 | 实现 LLMClient 抽象接口 | High | 0.5h | T2.1 | pending |
| T8.3 | 实现 MockLLMClient | High | 1h | T8.2 | pending |
| T8.4 | 实现 Scheduler 初始化 | High | 1h | T4.5, T5.5, T6.6, T7.4 | pending |
| T8.5 | 实现 submit 同步方法 | High | 2h | T8.4 | pending |
| T8.6 | 实现 submit_async 异步方法 | High | 2h | T8.4 | pending |
| T8.7 | 实现 _dispatch_loop 调度循环 | High | 3h | T8.4 | pending |
| T8.8 | 实现 _execute_request 执行逻辑 | High | 2h | T8.7 | pending |
| T8.9 | 实现 _cleanup_loop 清理循环 | Medium | 1h | T8.4 | pending |
| T8.10 | 集成 MetricsCollector | Medium | 2h | T8.9 | pending |
| T8.11 | 实现 start/stop 方法 | High | 1h | T8.10 | pending |
| T8.12 | 编写 Scheduler 单元测试 | High | 3h | T8.11 | pending |

## 阶段 9：集成与示例

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T9.1 | 创建基础使用示例 | High | 2h | T8.12 | pending |
| T9.2 | 创建集成测试 | High | 3h | T9.1 | pending |
| T9.3 | 更新 README.md | Medium | 2h | T9.2 | pending |

## 阶段 10：压力测试与优化

| 任务 ID | 任务名称 | 优先级 | 预估工时 | 依赖 | 状态 |
|---------|---------|--------|---------|------|------|
| T10.1 | 创建压力测试脚本 | Medium | 3h | T9.2 | pending |
| T10.2 | 性能测试与调优 | Medium | 4h | T10.1 | pending |
| T10.3 | 修复发现的问题 | High | 2h | T10.2 | pending |

## 汇总

| 阶段 | 任务数 | 预估总工时 |
|------|--------|-----------|
| 阶段 1：项目初始化 | 4 | 2h |
| 阶段 2：核心数据模型 | 3 | 4h |
| 阶段 3：Token 估算器 | 4 | 3h |
| 阶段 4：资源管理器 | 5 | 7.5h |
| 阶段 5：时间窗口限流器 | 5 | 9h |
| 阶段 6：队列管理器 | 6 | 8h |
| 阶段 7：监控指标 | 4 | 6h |
| 阶段 8：核心调度器 | 12 | 20.5h |
| 阶段 9：集成与示例 | 3 | 7h |
| 阶段 10：压力测试与优化 | 3 | 9h |
| **总计** | **53** | **76h** |

---

## 关键依赖关系

```
T1.1 (清空代码)
  ↓
T1.2 (目录结构) → T1.3 (依赖) → T1.4 (配置)
  ↓
T2.1 (数据模型) → T2.2 (错误类型) → T2.3 (模型测试)
  ↓
├─→ T3.1 (TokenEstimator) → T3.2 (SimpleEstimator) → T3.3 (tiktoken) → T3.4 (测试)
├─→ T4.1 (ResourceManager) → T4.2 (try_acquire) → T4.3 (release) → T4.4 (get_state) → T4.5 (测试)
├─→ T5.1 (滑动窗口) → T5.2 (RateLimiter) → T5.3 (TokenBucket) → T5.4 (get_state) → T5.5 (测试)
├─→ T6.1 (SceneQueue) → T6.2 (QueueManager) → T6.3 (enqueue) → T6.4 (dequeue) → T6.5 (cleanup) → T6.6 (测试)
└─→ T7.1 (MetricsCollector) → T7.2 (指标定义) → T7.3 (更新方法) → T7.4 (测试)
  ↓
T8.1 (SchedulerConfig) → T8.2 (LLMClient) → T8.3 (MockLLMClient)
  ↓
T8.4 (Scheduler初始化) → T8.5 (submit) → T8.6 (submit_async) → T8.7 (dispatch_loop) → T8.8 (execute) → T8.9 (cleanup_loop) → T8.10 (metrics) → T8.11 (start/stop) → T8.12 (测试)
  ↓
T9.1 (示例) → T9.2 (集成测试) → T9.3 (README)
  ↓
T10.1 (压力测试) → T10.2 (性能调优) → T10.3 (修复问题)
```
