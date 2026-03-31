# Tasks

- [x] Task 1: 优化 ResourceManager 资源管理逻辑
  - [x] SubTask 1.1: 修复 _calculate_total_demand 方法，使其能接收队列等待 token 作为参数
  - [x] SubTask 1.2: 优化 try_acquire 方法，明确资源充裕/紧张的判断逻辑
  - [x] SubTask 1.3: 为 ResourceManager 添加 can_acquire 预检查方法（不实际分配资源）
- [x] Task 2: 优化 QueueManager 队列调度逻辑
  - [x] SubTask 2.1: 添加 get_candidates 方法，获取所有队列的队首请求及其信息
  - [x] SubTask 2.2: 实现 select_best_candidate 方法，按优先级+入队时间选择最佳请求
  - [x] SubTask 2.3: 添加 get_total_waiting_tokens 方法，获取队列中等待的总 token 数
- [x] Task 3: 优化 Scheduler 调度流程
  - [x] SubTask 3.1: 重构 _try_dispatch 方法，使用预检查机制选择请求
  - [x] SubTask 3.2: 确保调度流程高效，避免不必要的重新入队
- [x] Task 4: 完善单元测试
  - [x] SubTask 4.1: 为 ResourceManager 添加单元测试，验证资源充裕/紧张场景
  - [x] SubTask 4.2: 为 QueueManager 添加单元测试，验证队列调度逻辑
  - [x] SubTask 4.3: 更新 Scheduler 单元测试，验证优化后的调度流程

# Task Dependencies
- Task 2 depends on Task 1 (ResourceManager 的 can_acquire 方法)
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 1, 2, 3
