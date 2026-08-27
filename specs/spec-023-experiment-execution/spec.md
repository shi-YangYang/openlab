# Spec：实验自动执行（spec-023）

## 元信息

- **Spec 编号**：`spec-023-experiment-execution`
- **状态**：`draft`
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-experiment-execution.md`
- **负责人**：协调开发 Agent

## 背景与动机

Phase 5 最后一环「实验自动执行与结果回传」留待至今。现在实验方案结构化数据、服务器管理、部署、命令执行、监控、Web 终端与 Agent 审批机制均已就绪，补上这一环即可让「文献 → 假设 → 实验 → 部署执行」全流程闭环。

## 目标

- 从实验方案一键发起部署与训练执行，人工每步可控或 Agent 全程主导。
- 执行过程日志实时可见，随时可切入 Web 终端人工接管。
- 失败自动重试一次，仍失败则暂停等人兜底。

## 范围

### 包含（In Scope）

- 后端执行器：步骤状态机 + 命令流式输出 + 运行记录持久化。
- 前端「执行」面板：双轨入口、步骤时间线、实时输出、失败处理控件。
- Agent 工具 `run_experiment`（复用既有审批机制）。
- 远程进程管理：记录训练进程 PID，支持停止。

### 不包含（Out of Scope）

- 结构化指标抽取与曲线图表（本期以日志为准）。
- 多机分布式训练编排、GPU 分配调度。
- 执行报告的云端存储。

## 需求描述

### 功能需求

#### 数据模型

- FR-1：新增 `experiment_runs` 持久化表：
  - 字段：`id`、`experiment_id`（关联方案）、`server_id`、`mode`（manual/agent）、`status`（pending/preparing/env_ready/running/paused/succeeded/failed/stopped）、`current_step`、`log_path`、`remote_workdir`、`pid`、`error`、`created_at`、`updated_at`。
  - 日志以本地文件存储（`data/experiment_runs/{run_id}.log`），DB 存路径不存全文。

#### 后端执行器

- FR-2：步骤流水线（顺序可跳过、每步命令可被自定义替换）：
  1. `sync_code` —— git clone 或 SFTP 上传（二选一，沿用 spec-008 能力）。
  2. `setup_env` —— 可配置的环境准备命令（默认模板：conda/pip 安装依赖），首次执行后记录已执行标记避免重复安装。
  3. `launch_training` —— 以 `nohup` 方式在远端后台启动训练命令，捕获并记录 PID；训练启动命令从实验方案推导（Agent 生成）或用户手填，持久化到 run 记录。
  4. `monitor_output` —— 通过轮询 `tail` 日志文件流式返回新增内容。
- FR-3：所有步骤经 paramiko `exec_command` 执行，stdout/stderr **逐行**通过 WebSocket 推送到前端实时渲染；同时追加写入本地 log 文件。
- FR-4：失败处理：任一步骤非零退出 → 自动重试 1 次 → 再失败则 run 置为 `paused`（`error` 记录失败原因），前端提供该步的三个操作：「改命令重试」「跳过此步」「终止任务」。
- FR-5：进程控制：`stop_run` 先向远端 PID 发 SIGTERM→宽限 10s→SIGKILL，并把 run 置为 `stopped`。
- FR-6：WS 协议（`WS /api/experiment-runs/ws?run_id=`）：服务端推 `{type:"step", step, status}`、`{type:"log", line, stream}`、`{type:"status", status, error?}`；客户端发 `{"type":"step_action","action":"retry|skip|kill","command?"}` 与 `{"type":"stop"}`。
- FR-7：REST：`POST /api/experiment-runs`（创建：experiment_id+server_id+mode+可选覆盖命令）、`GET /api/experiment-runs`（列表）、`GET /api/experiment-runs/{id}`（详情含日志尾部）、`DELETE /api/experiment-runs/{id}`（删除记录及日志）。

#### Agent 工具

- FR-8：新增 `run_experiment(experiment_id, server_id)` agent 工具：读取方案 → 调用执行器创建 run 并驱动整条流水线（环境准备命令由 LLM 依据方案与目标平台生成）→ 流水线进入 running 且训练健康启动（PID 存活）后向 agent 返回 run_id 与「如何查看进度」。危险等级 = 高（内部含远程命令，走既有审批）。
- FR-9：工具返回中包含 tail 日志片段，使 Agent 能向用户播报当前进展。

#### 前端

- FR-10：实验方案历史页每行新增「执行」按钮 → 打开执行面板：
  - 第一步选服务器（列出已有服务器，可先做连通性测试）；
  - 展示方案摘要与推导出的各步命令（可编辑）；
  - 「开始执行」（人工模式）或「交给 Agent」（跳转/调用 agent 主导）。
- FR-11：执行面板主体为步骤时间线 + 滚动日志区（自动滚底、可暂停滚动、支持关键词高亮）；步骤状态用图标区分（待执行/运行中/成功/失败-重试中/跳过/终止）。
- FR-12：失败暂停态显示三操作（FR-4）；运行态显示「停止任务」；全部完成后显示「已完成」并可查看完整日志。
- FR-13：历史运行列表（含状态/耗时/错误），点击载入详情与日志回放（读 log 文件）。

### 非功能需求

- NFR-1：远端命令执行统一带超时保护（sync/setup 步骤 30 分钟，monitor 轮询单次 10s），超时视为失败进入重试/暂停逻辑。
- NFR-2：日志文件写入采用追加模式；同一 run 的并发写须串行化。
- NFR-3：SSH 凭据不落日志；日志写入前经脱敏（复用 `_redact_secrets`）。
- NFR-4：agent 循环与执行器并发安全：同一 server_id 上多个 run 允许并存但互不干扰（各自 PID 独立管理）。
- NFR-5：`pytest tests -q` 与 `npm run build` 通过；执行器核心逻辑（状态迁移、PID 管理、日志切割）有单元测试（mock SSH）。

## 消息协议约定

见 FR-6（WS）。事件类型小写下划线命名，与既有风格一致。

## 后端接口草案

- `POST /api/experiment-runs` — 创建运行
- `GET /api/experiment-runs` / `GET /api/experiment-runs/{id}` / `DELETE /api/experiment-runs/{id}`
- `WS /api/experiment-runs/ws?run_id=` — 日志与控制通道
- Agent tools：`run_experiment`

## 依赖与前置条件

- spec-007（实验方案）、spec-008/009（服务器/部署/监控）、spec-016（终端，人工兜底入口）、spec-020（WS/agent 任务化模式参考）。

## 验收标准

详细步骤见 `acceptance.md`。

- 人工模式：创建 run → 逐步执行/跳过 → 训练拉起拿到 PID → 日志实时滚动 → 停止可控。
- Agent 模式：一句话发起 → 审批 → 自动走到 running → Agent 播报进展。
- 失败路径：故意让某步失败 → 重试 1 次 → paused → 改命令重试成功继续。
- 后端测试与前端 build 通过。

## 风险与开放问题

- 训练启动命令高度依赖具体代码库约定，首版以「LLM 推导 + 用户编辑确认」折中。
- nohup 后台进程跨 SSH 会话存活依赖服务器 shell 配置，个别机器可能需 tmux——首版文档说明，不做抽象层。
