# LLM Multi-Scene Scheduler - 模拟测试系统

这是一个完整的模拟测试系统，用于测试 LLM 多场景调度器在不同负载条件下的性能表现。

## 目录结构

```
tests/simulation/
├── __init__.py           # 模块导出
├── resource_pool.py      # 模拟 LLM 服务资源池
├── load_generator.py     # 多场景负载生成器
├── scenarios.py          # 测试场景定义
├── monitoring.py         # 监控和评估模块
├── visualization.py      # 可视化报告生成器
├── orchestrator.py       # 主模拟协调器
├── main.py               # 命令行入口
├── example_usage.py      # 使用示例
├── verify_components.py  # 组件验证脚本
└── README.md             # 本文档
```

## 组件说明

### 1. resource_pool.py - 模拟 LLM 服务资源池

- **LLMServiceInstance**: LLM 服务实例模型，包含处理能力、内存限制、延迟等规格
- **ResourcePoolManager**: 资源池管理器，支持动态分配/释放、实时监控
- **create_default_resource_pool()**: 创建默认的 5 个实例资源池

### 2. load_generator.py - 多场景负载生成器

- **TrafficPattern**: 多种流量模式（线性、指数、随机、正弦、突发、稳定）
- **TokenDistribution**: 多种 token 分布（均匀、正态、长尾、双峰）
- **LoadGenerator**: 负载生成器，支持场景级负载配置

### 3. scenarios.py - 测试场景定义

- **Scenario A**: 日间峰值（9:00-18:00）- 正弦波流量模式
- **Scenario B**: 夜间峰值（23:00-02:00）- 指数增长流量模式
- **Scenario C**: 极端突发 - 测试系统弹性
- **Scenario D**: 混合请求 - 长尾 + 小请求混合

### 4. monitoring.py - 监控和评估模块

- **ResponseTimeMetrics**: 响应时间指标（平均、P50、P75、P95、P99）
- **SuccessRateMetrics**: 成功率跟踪
- **ResourceMetrics**: 资源利用率（CPU、内存、网络）
- **ThroughputMetrics**: 系统吞吐量
- **MetricsCollector**: 指标收集器

### 5. visualization.py - 可视化报告生成器

- 使用 matplotlib/seaborn 生成可视化图表
- 响应时间分布图
- 成功率可视化
- 资源利用率图表
- 吞吐量可视化
- 综合 HTML 报告

### 6. orchestrator.py - 主模拟协调器

- 集成所有组件
- 场景运行器
- 结果导出功能

### 7. main.py - 命令行入口

提供命令行接口来运行模拟：

```bash
# 列出所有可用场景
python tests/simulation/main.py list

# 运行单个场景（使用 100x 时间加速）
python tests/simulation/main.py single scenario_c -t 100

# 运行所有场景
python tests/simulation/main.py all -t 100
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 验证组件

```bash
python tests/simulation/verify_components.py
```

### 3. 运行示例

```bash
python tests/simulation/example_usage.py
```

## 测试场景

### Scenario A - Daytime Peak (9:00-18:00)
- **持续时间**: 9 小时
- **流量模式**: 正弦波
- **预期成功率**: 95%
- **场景**: chat, qa, summarization, coding

### Scenario B - Nighttime Peak (23:00-02:00)
- **持续时间**: 3 小时
- **流量模式**: 指数增长
- **预期成功率**: 98%
- **场景**: chat, qa, creative

### Scenario C - Extreme Burst
- **持续时间**: 30 分钟
- **流量模式**: 突发
- **预期成功率**: 85%
- **场景**: api, web

### Scenario D - Mixed Requests
- **持续时间**: 2 小时
- **流量模式**: 稳定
- **预期成功率**: 92%
- **场景**: small_tasks, medium_tasks, large_tasks

## 输出结果

运行模拟后，将在 `simulation_results/` 目录下生成：

```
simulation_results/
└── scenario_a/
    ├── report.html              # 综合 HTML 报告
    ├── result.json              # JSON 格式结果
    ├── response_time_distribution.png
    ├── success_rate.png
    ├── resource_utilization.png
    └── throughput.png
```

## 代码风格

- 遵循现有项目代码风格
- 使用类型注解
- 使用 dataclass 定义数据结构
- 线程安全设计
