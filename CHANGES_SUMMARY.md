# LLM Multi-Scene Scheduler 修复摘要

## 修复日期
2026-04-01

## 问题发现与修复概述

本次修复针对 LLM 多场景调度器发现的多个关键问题进行了全面修复和增强。

---

## 一、问题汇总

### 1. 资源约束问题
- ❌ 低负载时场景可以突破自身配额
- ❌ 缺少并发数约束
- ❌ 缺少 worker capacity 检查
- ❌ 调度时缺少 rate limit 二次检查

### 2. 多场景调度问题
- ❌ 大请求阻塞小请求（头阻塞）
- ❌ 低优先级永久饥饿
- ❌ 仅依赖定时轮询

### 3. Oversell 问题
- ❌ 场景配额未始终强制执行

### 4. 排队机制问题
- ❌ 缺少全局队列上限
- ❌ 缺少重复入队检查
- ❌ 可能出现幽灵请求

### 5. 调度器问题
- ❌ 头阻塞问题
- ❌ 调度时缺少 rate limit 二次检查
- ❌ 仅依赖定时轮询

---

## 二、修复内容

### 修改的文件

1. `src/models.py`
2. `src/resource_manager.py`
3. `src/queue_manager.py`
4. `src/scheduler.py`
5. `tests/unit/test_scheduler_fixed_features.py` (新增)

### 详细修改

#### 1. src/models.py
- **GlobalConfig**: 添加 `max_concurrent_requests` 字段（默认 100）
- **SceneConfig**: 添加 `max_concurrent_requests` 字段（默认 50）
- **ResourceState**: 添加并发请求相关字段

#### 2. src/resource_manager.py
- **构造函数**: 添加 `max_concurrent_requests` 参数
- **新增字段**: 
  - `_used_concurrent_requests`: 全局并发请求计数
  - `_scene_concurrent_requests`: 场景级并发请求计数
  - `_scene_max_requests`: 场景最大并发请求配置
- **set_scene_config**: 同时设置场景最大请求数
- **_check_can_acquire**: 
  - 无条件检查场景配额（修复低负载时突破配额问题）
  - 添加全局并发请求数检查
  - 添加场景并发请求数检查
- **try_acquire**: 同时增加并发请求计数
- **release**: 同时减少并发请求计数
- **get_state**: 返回并发请求状态

#### 3. src/queue_manager.py
- **构造函数**: 
  - 添加 `global_queue_size` 参数（默认 10000）
  - 添加 `_active_request_ids` 集合防止重复入队
- **enqueue**:
  - 添加重复请求检查
  - 添加全局队列上限检查
  - 入队时记录 request_id
- **get_candidates**: 
  - 添加 `max_per_scene` 参数（默认 5）
  - 返回每个场景的多个候选者（修复头阻塞）
- **dequeue_specific_request**: 新增方法，支持从队列任意位置移除请求
- **dequeue_by_scene**: 出队时清理 request_id
- **cleanup_expired**: 清理时同时清理 request_id

#### 4. src/scheduler.py
- **SchedulerConfig**: 添加 `global_queue_size` 参数
- **Scheduler.__init__**:
  - ResourceManager 传入 `max_concurrent_requests`
  - QueueManager 传入 `global_queue_size`
  - 添加 `_dispatch_event` 用于事件驱动调度
- **_dispatch_loop**: 使用事件等待替代固定 sleep
- **_try_dispatch**:
  - 获取每个场景的多个候选者
  - 添加老化机制（每 30 秒提升优先级）
  - 调度时先调用 rate limiter 二次检查
  - 使用 `dequeue_specific_request` 移除特定请求
- **_execute_request**: 完成后触发调度事件

#### 5. tests/unit/test_scheduler_fixed_features.py (新增)
新增 7 个测试用例：
- `test_scene_quota_enforced_always`: 验证场景配额始终强制执行
- `test_concurrent_requests_limit`: 验证并发数限制
- `test_global_queue_limit`: 验证全局队列上限
- `test_duplicate_request_prevention`: 验证重复入队防止
- `test_no_head_blocking`: 验证头阻塞修复
- `test_aging_mechanism`: 验证老化机制
- `test_resource_manager_concurrent_requests`: 验证 ResourceManager 并发数功能

---

## 三、测试结果

### 单元测试
- **原有测试**: 12 个全部通过
- **新增测试**: 7 个全部通过
- **总计**: 19 个测试全部通过

```
tests/unit/test_scheduler.py: 6 passed
tests/unit/test_scheduler_comprehensive.py: 6 passed
tests/unit/test_scheduler_fixed_features.py: 7 passed
======================== 19 passed in 85.45s =========================
```

---

## 四、核心修复点

| 修复项 | 状态 | 说明 |
|--------|------|------|
| 1. 场景配额始终强制执行 | ✅ | 移除资源充裕条件，始终检查 |
| 2. 并发数约束实现 | ✅ | 全局和场景级并发数限制 |
| 3. 头阻塞问题修复 | ✅ | 多候选者选择 + 特定请求移除 |
| 4. 老化机制防止饥饿 | ✅ | 每 30 秒动态提升优先级 |
| 5. 事件驱动调度 | ✅ | Worker 完成后立即触发调度 |
| 6. 全局队列上限 | ✅ | 防止内存无限增长 |
| 7. 重复入队防止 | ✅ | request_id 去重 |
| 8. 调度时 rate limit 二次检查 | ✅ | 队列等待期间可能超限 |

---

## 五、Git 提交信息

```
commit 076f5a7
Author: 王述 <sugar@Sugars-MacBook-Pro.local>
Date:   2026-04-01

    fix: 修复多场景调度器的多个关键问题

    - 修复资源约束：场景配额始终强制执行，添加并发数约束
    - 修复多场景调度：头阻塞问题，添加老化机制防止饥饿
    - 修复调度器：添加事件驱动调度，调度时二次检查 rate limit
    - 修复排队机制：添加全局队列上限，重复入队检查
    - 新增测试：添加7个新测试用例验证修复功能
```

---

## 六、后续建议

1. **性能测试**: 在高负载场景下进行性能基准测试
2. **压力测试**: 验证在极端情况下的稳定性
3. **监控增强**: 添加更多内部指标用于问题排查
4. **配置调优**: 根据实际使用场景调整老化间隔、候选者数量等参数

---

## 七、已知限制

1. Rate limiter 使用滑动窗口，没有反向释放机制（这是滑动窗口的特性，不是 bug）
2. 老化机制的时间间隔固定为 30 秒，暂不支持动态配置

---

**修复完成日期**: 2026-04-01
