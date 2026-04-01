# LLM 多场景调度器 - 线上接入指南

## 概述

本指南将帮助你将 LLM 多场景调度器接入到线上 LLM 服务（如 OpenAI、Azure OpenAI、Claude 等）。

---

## 一、当前状态

### ✅ 已提供的框架

1. **LLMClient 抽象接口** ([src/scheduler.py](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/src/scheduler.py#L28-L30))
   ```python
   class LLMClient:
       def call(self, prompt, max_output_token):
           raise NotImplementedError
   ```

2. **MockLLMClient** - 用于测试
   - 模拟 LLM 响应
   - 支持延迟配置

3. **OpenAIClient** ([src/clients/openai_client.py](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/src/clients/openai_client.py)) - 官方 OpenAI 兼容实现

### ✅ 已提供的示例

- [examples/basic_usage.py](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/examples/basic_usage.py) - 基础使用示例
- [examples/production_usage.py](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/examples/production_usage.py) - 线上使用示例

---

## 二、快速接入 OpenAI

### 步骤 1：安装依赖

```bash
pip install openai
```

### 步骤 2：设置 API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 步骤 3：使用 OpenAIClient

```python
from src.clients import OpenAIClient
from src.scheduler import Scheduler, SchedulerConfig
from src.models import GlobalConfig, SceneConfig

llm_client = OpenAIClient(
    model="gpt-3.5-turbo",
    temperature=0.7,
    timeout=60.0,
)

scheduler = Scheduler(
    config=scheduler_config,
    llm_client=llm_client,
)
```

### 步骤 4：运行示例

```bash
python examples/production_usage.py
```

---

## 三、接入其他 LLM 服务

### 3.1 接入 Azure OpenAI

```python
from src.scheduler import LLMClient
from src.models import LLMResponse
import openai
import time

class AzureOpenAIClient(LLMClient):
    def __init__(self, api_key, endpoint, deployment_name, api_version="2024-02-15-preview"):
        self.client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self.deployment_name = deployment_name

    def call(self, prompt, max_output_token):
        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output_token,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            tokens_used=response.usage.total_tokens,
            duration=time.time() - start_time,
        )
```

### 3.2 接入 Claude (Anthropic)

```python
from src.scheduler import LLMClient
from src.models import LLMResponse
import anthropic
import time

class ClaudeClient(LLMClient):
    def __init__(self, api_key, model="claude-3-opus-20240229"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def call(self, prompt, max_output_token):
        start_time = time.time()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_output_token,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            content=response.content[0].text,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            duration=time.time() - start_time,
        )
```

### 3.3 接入自建 LLM 服务

```python
from src.scheduler import LLMClient
from src.models import LLMResponse
import requests
import time

class SelfHostedLLMClient(LLMClient):
    def __init__(self, base_url, model="your-model-name"):
        self.base_url = base_url
        self.model = model

    def call(self, prompt, max_output_token):
        start_time = time.time()
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_output_token,
            },
            timeout=60,
        )
        data = response.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            tokens_used=data["usage"]["total_tokens"],
            duration=time.time() - start_time,
        )
```

---

## 四、配置说明

### 4.1 GlobalConfig 配置

| 字段 | 说明 | 推荐值 |
|------|------|---------|
| `total_concurrent_tokens` | 全局并发 Token 容量 | 根据 LLM 服务限制 |
| `global_tpm` | 全局 TPM 限制 | 根据 API 配额 |
| `global_qpm` | 全局 QPM 限制 | 根据 API 配额 |
| `worker_count` | Worker 数量 | 4-10（根据并发需求） |
| `max_concurrent_requests` | 最大并发请求数 | 20-100 |

### 4.2 SceneConfig 配置

| 字段 | 说明 |
|------|------|
| `scene_id` | 场景唯一标识 |
| `priority` | 优先级（数字越小越高） |
| `max_concurrent_tokens` | 场景最大并发 Token |
| `max_concurrent_requests` | 场景最大并发请求数 |
| `scene_tpm` / `scene_qpm` | 场景级 TPM/QPM 限制 |
| `queue_size` | 场景队列大小 |
| `timeout` | 请求超时时间 |

---

## 五、监控与运维

### 5.1 Prometheus 指标

调度器内置了完整的 Prometheus 指标：

```python
from src.metrics import MetricsCollector

metrics = MetricsCollector()
scheduler = Scheduler(..., metrics_collector=metrics)

# 在你的服务中暴露指标
from prometheus_client import generate_latest

@app.route("/metrics")
def metrics_endpoint():
    return generate_latest(metrics.registry), 200, {"Content-Type": metrics.content_type}
```

### 5.2 关键监控指标

| 指标 | 告警阈值 |
|------|---------|
| `llm_scheduler_queue_length` | > 100 |
| `llm_scheduler_available_concurrent_tokens` | < 10% |
| `llm_scheduler_requests_timeout` | 超时率 > 5% |
| `llm_scheduler_requests_rate_limited` | 限流率 > 10% |

---

## 六、最佳实践

### 6.1 配置超卖

超卖配置建议：场景 max_concurrent_tokens 之和 ≤ 全局容量的 1.5-2 倍

```python
# 示例：全局容量 100,000，场景合计 150,000（1.5 倍超卖）
global_config = GlobalConfig(total_concurrent_tokens=100000, ...)
scene_configs = [
    SceneConfig(scene_id="chatbot", max_concurrent_tokens=60000, priority=1),
    SceneConfig(scene_id="analytics", max_concurrent_tokens=50000, priority=2),
    SceneConfig(scene_id="background", max_concurrent_tokens=40000, priority=3),
]
```

### 6.2 优先级设置

| 场景类型 | 推荐优先级 |
|---------|-----------|
| 在线客服、实时交互 | 1 |
| 数据分析、批量任务 | 2 |
| 后台作业、非实时 | 3 |

### 6.3 队列大小设置

- 高优先级场景：1000-2000
- 中优先级场景：500-1000
- 低优先级场景：200-500

---

## 七、故障排查

### 问题 1：请求总是被限流

**检查清单：**
1. 确认 TPM/QPM 配置是否合理
2. 检查 `rate_limit_state` 中的使用量
3. 确认 LLM 服务配额是否足够

### 问题 2：低优先级场景饥饿

**解决方案：**
- 当前已实现老化机制（每 30 秒提升优先级）
- 可以考虑调整低优先级场景的 `max_concurrent_tokens`
- 监控队列等待时间

### 问题 3：内存占用过高

**检查清单：**
1. 确认 `global_queue_size` 配置合理
2. 检查各场景 `queue_size`
3. 确认没有大量超时请求堆积

---

## 八、参考资料

- [CHANGES_SUMMARY.md](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/CHANGES_SUMMARY.md) - 修复摘要
- [design/spec.md](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/design/spec.md) - 技术方案文档
- [examples/production_usage.py](file:///Users/sugar/Desktop/code/LLM-MultiScene-Scheduler/examples/production_usage.py) - 线上使用示例
