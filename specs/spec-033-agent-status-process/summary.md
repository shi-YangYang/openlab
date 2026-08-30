# Summary：spec-033-agent-status-process

## 完成日期

2026-08-30

## 实施内容

Agent 运行状态与过程展示重构（参考 opencode/codex）。

### 后端（5 文件 + 测试）

- `db/agent.py` + `db/__init__.py`：新增 `reset_agent_session_running()`（全量清 running/status）。
- `app/app.py`：lifespan startup 调用清理——修复进程崩溃后 `running=1/status='thinking'` 永久残留（僵尸"思考中"）。
- `agent/sessions.py`：`normalize_history` 重写——输出 `{role, content, time, model, intermediate, toolCalls}`；中间 AI 消息判定（段内非末条/带 tool_calls → intermediate）；`_rebuild_tool_calls()` 按 tool_call_id 匹配 ToolMessage 重建工具卡片（status 按缺失/内容前缀推断 done/error）；空文本带工具的 AI 消息不再丢弃。
- `schemas.py`：AgentSessionMessage 扩展两字段（驼峰直出）。
- `tests/test_agent_history.py`（新建 9 用例，含嵌套 TestClient 重放 lifespan 验证僵尸态清理）；`test_agent.py` 一处 message_count 断言适配。

### 前端（6 文件）

- `useAgentState.ts`：流式回合切分——token 仅 append 到"无工具且未标记"的 turn；tool_call 先补标既有 turn 为 intermediate 再归属；done 末轮为最终回复；pending_approval 不再清 running（过程保持展开）；statusLabel 重构为 activity/stopPending；refreshDetail 映射新字段（旧数据兜底）。
- `AgentRunningIndicator.tsx`（新建）：内联活动指示器——`思考中 · Ns` / `执行中：<tool> · Ns` / `正在回复…` / `等待你的确认` / `正在停止…`，1s 计时跳动，脉冲状态点，完成立即消失；空列表时置于顶部。
- `AgentChatMessages.tsx`：删除底部独立 statusRow；连续 intermediate 回合分组为 Collapse「思考与过程 · N 步」（运行中展开、done 自动收起、手动展开优先）；最终回复独立渲染（toolbar 保留）。
- `types.ts` / `AgentPage.tsx` / `AgentChatInput.tsx` / `module.css`：类型与传参适配、新样式、删 statusRow。

## 验证结果

- pytest 全量 **378 passed**（既有 369 + 新增 9）；`npm run build` 通过。
- 验收独立核对：FR-1~FR-9 全 PASS；AC-1~AC-11 全 PASS / CODE-REVIEW-PASS；双 e2e（僵尸态清理、多轮 intermediate/toolCalls 断言）；无超范围改动、无密钥、无调试残留。

## 已知低优先级遗留（不阻塞）

1. 折叠分组 key 用消息索引，消息追加时手动展开状态可能串组（纯展示层）。
2. 历史中 run 以工具调用收尾（拒绝/中断）时整段全折叠无结论（符合规则字面语义）。

## 遗留事项

- 建议用户实际运行体验：多轮任务的实时过程展开 → 完成自动折叠、内联计时指示器。
