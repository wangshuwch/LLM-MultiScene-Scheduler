# 模拟测试故障排查指南

## 问题描述

运行 `python tests/simulation/main.py all -t 100` 命令后，程序长时间运行（超过1小时）仍未完成。

---

## 🔴 立即操作

### 1. 终止当前进程

```bash
# 查找进程
ps aux | grep "python tests/simulation/main.py"

# 或查找所有 Python 进程
ps aux | grep python

# 终止进程（替换 <PID> 为实际进程 ID）
kill -9 <PID>
```

---

## 📊 问题分析

### 根本原因

#### 原因 1：时间缩放没有正确应用

**文件**: [tests/simulation/orchestrator.py](tests/simulation/orchestrator.py)

**问题代码** (L228-L230):
```python
# 即使使用了时间缩放，这个循环也会等待真实时间！
while self._running and (time.time() - start_time) < sim_duration:
    time.sleep(0.1)
```

**说明**：即使设置 `time_scale=100`，这段代码仍然会等待真实时间！

#### 原因 2：场景持续时间太长

| 场景 | 持续时间 | 100x 时间缩放理论耗时 |
|------|---------|---------------------|
| Scenario A (Daytime Peak) | 32,400 秒 (9 小时) | 324 秒 (5.4 分钟) |
| Scenario B (Nighttime Peak) | 10,800 秒 (3 小时) | 108 秒 (1.8 分钟) |
| Scenario C (Extreme Burst) | 1,800 秒 (30 分钟) | 18 秒 |
| Scenario D (Mixed Requests) | 7,200 秒 (2 小时) | 72 秒 |

**总计**：约 **522 秒 (8.7 分钟)**（理论上）

#### 原因 3："等待请求完成"阶段可能卡死

**问题代码** (L231-L238):
```python
print("Simulation completed, waiting for requests to finish...")
self._request_queue.join()  # ← 这里可能永远等待！
```

---

## 🔍 排查步骤

### 步骤 1：检查进程状态

```bash
# 查看进程是否还在运行
ps aux | grep -E "(python|simulation)"

# 查看进程树
pstree -p <PID>

# 查看进程资源使用
top -p <PID>
```

### 步骤 2：检查系统资源

```bash
# CPU 使用率
top

# 内存使用
free -h

# 磁盘 I/O
iostat -x 1

# 查看是否有进程处于 D 状态（不可中断的睡眠，通常是 I/O 等待）
ps aux | awk '$8 ~ /D/ { print $0 }'
```

### 步骤 3：检查输出目录

```bash
# 查看是否有输出文件
ls -la simulation_results/

# 如果有输出，查看内容
ls -la simulation_results/scenario_a/ 2>/dev/null || echo "No output yet"
```

---

## 💡 解决方案

### 方案 1：使用快速测试（推荐）

先运行快速测试验证系统是否正常工作：

```bash
# 运行快速测试
python tests/simulation/quick_test.py

# 或只运行一个短场景
python tests/simulation/main.py single scenario_c -t 1000
```

### 方案 2：使用更高的时间缩放

```bash
# 使用 1000x 时间缩放，而不是 100x
python tests/simulation/main.py single scenario_a -t 1000
```

### 方案 3：逐个场景运行，而不是运行 all

```bash
# 先运行 Scenario C（最短，30分钟 → 18秒@100x）
python tests/simulation/main.py single scenario_c -t 100

# 验证没问题后再运行其他场景
```

### 方案 4：临时修改场景持续时间（开发/调试用）

如果需要，可以临时修改场景持续时间。编辑 [tests/simulation/scenarios.py](tests/simulation/scenarios.py)，将 `duration_seconds` 改小。

---

## 📋 推荐的测试顺序

### 第 1 步：验证组件

```bash
python tests/simulation/verify_components.py
```

### 第 2 步：运行快速测试

```bash
python tests/simulation/quick_test.py
```

### 第 3 步：单个场景测试

```bash
# 从最短的场景开始
python tests/simulation/main.py single scenario_c -t 1000

# 然后运行其他场景
python tests/simulation/main.py single scenario_d -t 1000
python tests/simulation/main.py single scenario_b -t 1000
python tests/simulation/main.py single scenario_a -t 1000
```

### 第 4 步：最后运行 all（如果需要）

```bash
# 只在单个场景都没问题后再运行 all
python tests/simulation/main.py all -t 1000
```

---

## 🎯 如果必须运行完整测试

如果确实需要运行所有 4 个场景的完整测试：

### 选项 A：增加时间缩放

```bash
# 使用 1000x 而不是 100x
python tests/simulation/main.py all -t 1000
```

### 选项 B：后台运行并重定向输出

```bash
# 后台运行，输出到日志文件
nohup python tests/simulation/main.py all -t 1000 > simulation.log 2>&1 &

# 查看日志
tail -f simulation.log
```

### 选项 C：定期检查并超时终止

```bash
#!/bin/bash
# run_simulation_with_timeout.sh

TIMEOUT=3600  # 1小时超时
python tests/simulation/main.py all -t 1000 &
PID=$!

# 等待或超时
(
    sleep $TIMEOUT
    kill $PID 2>/dev/null && echo "Simulation timed out after $TIMEOUT seconds"
) &
wait $PID
```

---

## 📝 总结

| 建议 | 说明 |
|-----|------|
| ❌ 不要运行 `all -t 100` | 太慢了，可能需要 8.7 分钟以上 |
| ✅ 先运行 `quick_test.py` | 快速验证系统 |
| ✅ 逐个场景运行 | 从最短的场景开始 |
| ✅ 使用 `-t 1000` | 1000x 时间缩放更快 |
| ✅ 后台运行并记录日志 | 方便调试 |

---

## 🆘 如果仍然卡死

如果按照上述建议仍然卡死，请检查：

1. 有没有错误日志？
2. 系统资源（CPU/内存/磁盘）是否耗尽？
3. 是否有其他进程冲突？
