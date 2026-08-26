# Spec 020 总结

## 元信息

- **Spec 编号**：`spec-020-agent-streaming`
- **状态**：completed（已完成）
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-agent-streaming.md`

## 目标

1. Agent 对话流式实时输出，事件驱动替代轮询。
2. 支持随时停止/中断运行中的任务。
3. 消息复制、代码块复制、会话导出 Markdown。
4. 上下文接近上限自动压缩历史。

## 技术栈

- 后端：WebSocket 单通道双向（`WS /api/agent/ws`），agent 循环改 `astream` 分片 + emit 回调任务化（AgentRunner）；上下文压缩模块 compaction.py；导出端点。
- 前端：useAgentChannel hook（连接管理 + 指数退避重连）+ AgentPage 事件驱动重构。
- 删除旧 `POST /api/agent/chat|approve` REST 端点。

## 需求清单

- FR-1~3：WS 通道与事件协议、astream 流式、审批走 WS。
- FR-4：停止中断（interrupted 状态、部分内容保留）。
- FR-5：上下文自动压缩（80% 阈值、摘要替换、失败跳过）。
- FR-6：会话导出 Markdown（脱敏）。
- FR-7~8：前端传输层重构与复制/导出交互。

## 验收结果

- 实施（含一次中断后续接）：后端 `pytest tests -q` → **269 passed**；前端 `npm run build` 通过。
- 验收：AC-1~AC-5 + 回归全部 **PASS**；协议与决策表逐项一致；旧端点确认删除；安全核查通过。
- 实施期间顺带修复两个真 bug：① `_build_bound_llm` 抛错导致 running 卡 True（已修并有回归测试）；② run_approve 不发 status/tool_call 事件（已补）。

## 决策引用

- `.ai/decisions/2026-08-27-agent-streaming.md`

## 使用方式

- Agent 页发送即实时逐字输出；工具执行状态实时刷新；危险操作弹窗经 WS 审批。
- 运行中「发送」变「停止」，点击即中断，已生成内容保留可继续对话。
- 每条消息 hover 复制；代码块右上角复制；头部「导出 Markdown」下载整段会话。
- 长对话接近模型上下文 80% 自动压缩早期历史并提示「已压缩早期历史」。

## 遗留问题 / 已知限制

1. 停止在「步与步之间」生效：正在执行的单个工具会先执行完；若 stop 恰落在当步 token 流式中途，该步未完成的分片不入库（已完成步骤的回复与工具记录均保留）。
2. 新建会话首条消息收到 session 事件后会触发一次通道快速重建（本地毫秒级，后台任务不受影响）。
3. 个别网关若不支持分片流式，退化为 done 直发全文（协议不变）；Reasoning 思维链展示、消息编辑重试、会话搜索等未纳入本期。
