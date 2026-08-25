# 实施计划：Agent 核心（spec-010）

## 任务拆分

1. 工具封装：把现有能力封装成 LangChain 工具（StructuredTool，含 name/description/输入 schema）。
2. agent 循环：手动驱动 tool-calling agent（不用 AgentExecutor 自动循环，以便在危险工具前暂停/恢复）。
3. 会话管理：session 存储（内存或 SQLite），保存对话历史 + 待确认状态。
4. agent API：`POST /api/agent/chat`（返回回复 + 工具调用日志 + 待确认）。
5. 确认机制：`POST /api/agent/approve`（危险工具 run_command/deploy_code 暂停 → 确认后执行/拒绝后跳过）。
6. 前端 Agent 页面：消息输入、对话展示、工具调用日志、进度、危险命令确认弹窗。
7. 测试。

## 实施顺序

工具封装 → 手动 agent 循环 → 会话 → chat API → 确认机制 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/`（新增 agent 模块：tools.py、agent.py，扩展 main/schemas）。
- `frontend/src/`（新增 AgentPage，扩展 App 导航、api/types）。
- `tests/` 新增 agent 测试（mock LLM）。

## 技术要点

- 工具用 LangChain `StructuredTool.from_function` 或 `@tool`，每个工具有清晰的 name/description/args_schema；工具标 `dangerous` 属性（run_command、deploy_code）。
- 手动 agent 循环：调用 `create_tool_calling_agent` 产出的 agent（`agent.invoke` 返回 tool_calls 或最终回复），逐次执行工具、追加 ToolMessage，循环直到最终回复。
- 危险工具：在循环中检测到 dangerous 工具调用 → 存 session 的 pending 状态 → 返回前端「待确认」→ `POST /api/agent/approve` 继续/拒绝。
- 会话存内存 dict（session_id → messages + pending），单用户本地场景足够。
- 工具内部直接调用现有后端函数，慢操作 await 完成或返回状态+进度，带超时。
- 前端 Agent 页：聊天界面 + 工具调用日志 + 危险命令确认弹窗（允许/拒绝）。

## 风险与应对

- LLM 工具选择不准确：工具 description 写清楚 + 提供示例。
- 慢工具超时：设置合理超时，返回状态让 agent 可重试/继续。
- 暂停/恢复：会话保存完整 messages，approve 后从断点继续循环。
