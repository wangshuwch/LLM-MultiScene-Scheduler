# Checklist

## ResourceManager 优化检查项
- [x] _calculate_total_demand 方法正确接收并使用队列等待 token 参数
- [x] try_acquire 方法在资源充裕时不检查场景 max_tokens
- [x] try_acquire 方法在资源紧张时检查场景 max_tokens
- [x] can_acquire 预检查方法正确实现（不实际分配资源）
- [x] ResourceManager 单元测试通过

## QueueManager 优化检查项
- [x] get_candidates 方法正确获取所有队列的队首请求
- [x] select_best_candidate 方法按优先级+入队时间正确选择请求
- [x] get_total_waiting_tokens 方法正确返回队列中等待的总 token 数
- [x] QueueManager 单元测试通过

## Scheduler 优化检查项
- [x] _try_dispatch 方法使用预检查机制选择请求
- [x] 调度流程高效，无不必要的重新入队
- [x] 资源充裕时场景能突破 max_tokens 限制
- [x] 资源紧张时高优先级场景优先获得资源
- [x] Scheduler 单元测试通过
