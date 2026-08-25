# 实施计划：Agent 专项升级（spec-012）

## 任务拆分

1. 补齐工具：历史查询（只读）、服务器 CRUD（危险）、SFTP 上传（危险）。
2. 沙箱模块：`backend/app/agent/sandbox.py`（每会话目录、subprocess、超时、无密钥 env）。
3. 动态工具：`run_python_code`、`run_shell_command`（走沙箱，危险）。
4. 状态细分：会话 `status` 字段 + agent 循环中更新（thinking/executing:<tool>）+ 步骤计数。
5. 前端：轮询展示细分状态（思考中 / 执行中：工具名 第 N 步）。
6. 测试。

## 实施顺序

沙箱 → 补齐工具 → 动态工具 → 状态字段 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/agent/tools.py`（新增工具）、`sandbox.py`（新增）、`agent.py`（状态更新）。
- `backend/app/database.py`、`sessions.py`、`schemas.py`、`main.py`（status 字段）。
- `frontend/src/components/AgentPage.tsx`、`api.ts`、`types.ts`。
- `tests/` 新增用例。

## 技术要点

- 沙箱：`data/sandbox/<session_id>/` 作为 cwd；`subprocess.run(..., timeout=60, capture_output=True)`；env 只传 PATH/HOME 等白名单，不含密钥。
- 动态工具：`run_python_code` 用 `sys.executable -c`，`run_shell_command` 用 `shell=True`，均走沙箱、标 dangerous。
- 历史查询工具：直接包装 `database.list_search_history` / `list_innovations` / `list_reviews` / `list_experiments` 等，只读。
- 服务器 CRUD：包装 `servers.add/update/delete`，标 dangerous，返回脱敏。
- 状态：`agent_sessions.status`（TEXT），agent 循环 `llm.ainvoke` 前置 `thinking`、执行工具前置 `executing:<tool>`；步骤计数随 status 或单独字段。
- 前端：轮询 `GET /api/agent/sessions/{id}`，解析 status 展示。

## 风险与应对

- subprocess 隔离非强隔离：限制 env + cwd + 超时，文档说明局限。
- 状态高频写 DB：可接受（个人本地）。
