# Tasks

- [x] Task 1: 创建 SystemStateAnalyzer 组件
  - [x] SubTask 1.1: 定义 SystemState 数据结构（负载等级、瓶颈资源等）
  - [x] SubTask 1.2: 实现状态分析逻辑（整合 ResourceState、QueueState、RateLimitState）
  - [x] SubTask 1.3: 实现负载等级判断（低/中/高负载）
  - [x] SubTask 1.4: 实现瓶颈资源识别
- [x] Task 2: 增强调度器配置
  - [x] SubTask 2.1: 添加调度策略配置（负载阈值等）
  - [x] SubTask 2.2: 支持动态调整配置
- [x] Task 3: 增强调度决策逻辑
  - [x] SubTask 3.1: 集成 SystemStateAnalyzer 到调度器
  - [x] SubTask 3.2: 实现基于负载等级的调度策略
  - [x] SubTask 3.3: 实现基于限流状态的预检查
- [x] Task 4: 增强可观测性
  - [x] SubTask 4.1: 添加调度决策日志
  - [x] SubTask 4.2: 添加系统状态分析指标
- [x] Task 5: 完善单元测试
  - [x] SubTask 5.1: 为 SystemStateAnalyzer 添加单元测试
  - [x] SubTask 5.2: 为增强的调度器添加单元测试

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 1, 2, 3, 4
