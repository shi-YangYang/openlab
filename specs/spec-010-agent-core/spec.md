# Spec：Agent 核心（spec-010）

## 元信息

- **Spec 编号**：`spec-010-agent-core`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-agent-core.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`
- **负责人**：协调开发 Agent

## 背景与动机

项目定位是「科研 Agent 框架」，但目前「agent」只是 LLM 文本生成（分析/创新/实验），真正「自主调用工具把科研流程串起来」的能力缺失。spec-010 把现有后端能力封装成工具，交给 LLM agent 自主编排执行，实现端到端的科研自动化。

## 目标

- 封装全部现有能力为 LLM 工具。
- 构建 agent 循环：给定目标，自主规划步骤、调用工具、串起结果。
- 支持任务式（给目标自主执行）与对话式。
- 危险操作（执行命令/部署）需用户确认后才执行。
- 前端提供 Agent 界面：输入 + 对话 + 工具调用执行日志 + 进度。

## 范围

### 包含（In Scope）

- 工具封装（全量）。
- agent 循环（tool calling）。
- 会话管理。
- agent API。
- 前端 Agent 页面。

### 不包含（Out of Scope）

- 工具执行的安全确认机制（后续）。
- 流式输出（首版可用轮询/整体返回）。

## 需求描述

### 功能需求

- FR-1：封装全量工具，至少包括：
  - 文献：`search_papers`、`search_by_topic`、`download_papers`、`list_downloaded_papers`
  - 分析：`analyze_paper`、`review_papers`、`generate_innovation_points`、`design_experiment`
  - 服务器：`list_servers`、`test_server_connection`、`deploy_code`、`run_command`、`monitor_server`
- FR-2：agent 循环：LLM 推理 → 调用工具 → 观察结果 → 继续，直到产出最终回答。
- FR-3：任务式与对话式交互（同一个 agent 循环）。
- FR-4：会话管理（session id 关联多轮对话历史）。
- FR-5：后端 agent API（如 `POST /api/agent/chat`：session_id + message → 回复 + 工具调用日志）。
- FR-6：前端「Agent」页面：消息输入、对话展示、工具调用执行日志、进度。
- FR-7：工具调用日志展示（工具名、参数、结果摘要）。
- FR-8：危险命令确认：`run_command`、`deploy_code` 调用前暂停 agent 循环，返回「待确认」给前端，用户确认后才执行；拒绝则跳过并反馈 agent。
- FR-9：确认接口：`POST /api/agent/approve`（session_id + approve 布尔），确认后继续执行、拒绝后跳过。

### 非功能需求

- NFR-1：复用 LangChain ChatOpenAI + OpenAI 兼容配置。
- NFR-2：密钥安全沿用（不入库、不打印、脱敏）。
- NFR-3：慢工具（下载/分析/创新/实验）调用需等待完成或返回状态，超时保护。

## 数据结构约定

工具调用日志（示意）：

```json
{"tool": "search_papers", "args": {"query": "..."}, "result": "命中 10 篇", "status": "done"}
```

会话：`agent_sessions`（session_id、messages 历史），可存内存或 SQLite。

## 后端接口草案

- `POST /api/agent/chat`（body: session_id?, message）→ `{session_id, reply, tool_calls: [{tool, args, result, status}], pending_approval?}`。
- `POST /api/agent/approve`（body: session_id, approve）→ 继续执行或跳过，返回同 chat 的结果结构。

## 依赖与前置条件

- spec-001~009 的后端能力（arxiv/analysis/innovation/experiment/servers/ssh）。
- LangChain（langchain + langchain-openai 已在依赖中）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- agent 执行命令/部署是高权限操作：由 FR-8/9 的确认机制拦截（需暂停/恢复 agent 循环，手动驱动循环而非 AgentExecutor 自动循环）。
- 慢工具等待时间较长，需超时与进度反馈。
- 工具选择准确率依赖 LLM 能力与工具描述质量。
