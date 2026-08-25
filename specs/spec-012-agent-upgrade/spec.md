# Spec：Agent 专项升级（spec-012）

## 元信息

- **Spec 编号**：`spec-012-agent-upgrade`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-agent-upgrade.md`、`.ai/decisions/2026-08-24-agent-core.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-010/011 已实现 Agent 核心与会话管理，但能力覆盖不全（历史查询、服务器增删改、SFTP 上传未工具化），agent 无法自建临时工具，且运行状态只有笼统的「正在执行」。spec-012 做专项升级。

## 目标

- 补齐缺失的工具（历史查询、服务器增删改、SFTP 上传）。
- agent 可执行 Python 代码与本地 shell（每会话独立沙箱）。
- agent 状态细分为「思考中」「执行中（含工具名与步骤）」并前端展示。

## 范围

### 包含（In Scope）

- 工具补齐 + 动态代码/命令执行 + 沙箱 + 状态细分。

### 不包含（Out of Scope）

- Docker 级隔离。
- 跨会话共享状态。

## 需求描述

### 功能需求

- FR-1：历史记录查询工具（搜索历史列表/详情、创新点列表、综述列表、实验列表，只读）。
- FR-2：服务器增删改工具（create/update/delete，凭据脱敏，危险需确认）。
- FR-3：SFTP 上传部署工具（local_path + remote_path，危险需确认）。
- FR-4：Python 代码执行工具 `run_python_code`（危险）。
- FR-5：本地 shell 命令执行工具 `run_shell_command`（危险）。
- FR-6：每会话独立沙箱工作目录（`data/sandbox/<session_id>/`）。
- FR-7：沙箱执行：subprocess + 超时 + 剥离密钥的环境变量 + 目录隔离。
- FR-8：agent 状态细分（thinking / executing:<tool>，含步骤计数），持久化到会话。
- FR-9：前端轮询并展示细分状态（思考中 / 执行中：工具名 第 N 步）。

### 非功能需求

- NFR-1：代码/命令执行安全（超时、目录隔离、无密钥环境）。
- NFR-2：凭据安全沿用（不入库、不打印、脱敏）。

## 数据结构约定

会话状态：`agent_sessions` 表 `running`（0/1）+ 新增 `status`（TEXT，如 `thinking` / `executing:search_papers`）。

## 后端接口草案

- 复用 `POST /api/agent/chat`、`POST /api/agent/approve`。
- `GET /api/agent/sessions/{id}` 详情返回 `status`。

## 依赖与前置条件

- spec-010（工具框架、agent 循环）、spec-011（会话状态轮询）。
- Python `subprocess`（标准库，无新依赖）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 代码执行安全依赖 subprocess 隔离与超时，非强隔离。
- 状态更新的并发与刷新一致性。
