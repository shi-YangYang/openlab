# Spec 023 实施计划

## 概览

后端执行器（状态机 + WS 日志流）与前端执行面板为两大主体，Agent 工具为胶水。分 4 批次。

## 批次划分

### 批次 1：数据模型与执行器核心

- `backend/app/database.py`：`experiment_runs` 表（`_migrate` 自动建表）；CRUD 函数 `create_experiment_run / get_experiment_run / list_experiment_runs / update_experiment_run_status / delete_experiment_run`。
- 新建 `backend/app/experiment_runner.py`：
  - 步骤常量与状态机迁移表；
  - `_run_step(run, step, command)`：paramiko exec 逐行读输出 → 回调（写日志 + emit）→ 返回 exit code；重试包装；
  - PID 管理：launch 后从远端回显解析 PID 存 DB；`stop_remote_process(server, pid)` SIGTERM→10s→SIGKILL；
  - `ExperimentRunDriver` 类：驱动整条流水线（asyncio task，参考 spec-020 AgentRunner 模式），暴露 `retry_step/skip_step/kill/stop`。
- 日志：`data/experiment_runs/{run_id}.log` 追加写，写入前 `_redact_secrets`。
- 单测：mock SSH（参照 tests/test_ssh.py 风格）覆盖状态迁移、重试、PID 解析、日志追加、脱敏。

### 批次 2：REST 与 WS 接口

- `backend/app/main.py`：
  - `POST/GET/DELETE /api/experiment-runs*` 三个 REST 端点；
  - `WS /api/experiment-runs/ws?run_id=`：attach 到对应 Driver 的广播；收 `step_action`/`stop` 转发 Driver；断开不影响运行。
- 创建端点入参校验：experiment_id/server_id 必须存在。
- 测试：REST CRUD + WS 基本事件序列（stub SSH）。

### 批次 3：Agent 工具

- `backend/app/agent/tools.py`：新增 `run_experiment(experiment_id: int, server_id: int) -> dict`：
  - 读方案 → 通过 ExperimentRunner 生成默认步骤命令（setup/launch 由 LLM 在工具内部二次调用生成：输入方案 JSON+目标平台信息）→ create run → 后台启动 Driver → 立即返回 run_id + 初始状态 + 使用说明（含如何 stop）；
  - 危险等级高；注册进 TOOLS 列表。
- 测试：FakeLLM 下 run_experiment 正确创建 run 并返回结构。

### 批次 4：前端执行面板

- `frontend/src/types.ts` / `api.ts`：ExperimentRun 类型 + REST 封装 + WS URL helper。
- 新建 `frontend/src/components/ExperimentRunPanel.tsx`：
  - 创建视图：选服务器下拉（带「测试连接」）、展示方案摘要、四个步骤的命令编辑框（默认由后端推导返回，可改）、模式选择（人工开始 / 复制 Agent 提示词跳转 agent 页）；
  - 运行视图：左侧步骤时间线（图标状态）、右侧滚动日志区（自动滚底开关 + 暂停 + 关键词高亮计数）、底部操作条（随状态切换：停止 / 重试此步 / 跳过 / 改命令重试弹窗）；
  - 复用 useAgentChannel 的重连心智实现 run ws 客户端（可抽公共小工具或独立 hook）。
- `frontend/src/components/ExperimentHistoryList.tsx`：每行加「执行」按钮打开面板（新路由 `/experiments/run/:id?run=` 或 Modal 承载，取 Modal 简单）。
- 历史运行列表 Tab：列出 runs，点击载入详情/日志回放（GET 详情接口取 tail）。

## 文件清单

### 后端
- `database.py`、`experiment_runner.py`（新建）、`main.py`
- `agent/tools.py`

### 前端
- `types.ts`、`api.ts`
- `components/ExperimentRunPanel.tsx`（新建）
- `components/ExperimentHistoryList.tsx`
- 可选：`hooks/useRunChannel.ts`

### 测试
- `tests/test_experiment_runner.py`（新建）
- `tests/test_api.py` 补 experiment-runs 用例
- `tests/test_agent_tools.py` 或既有 agent 工具测试补 run_experiment

## 验证方式

- 后端 `pytest tests -q`；前端 `npm run build`；手工冒烟见 acceptance.md（真实服务器跑一个 echo/python 训练脚本验证全链路）。
