# spec-012 汇总：Agent 专项升级

> 本文档汇总 spec-012 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-012-agent-upgrade`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-agent-upgrade.md`

## 背景与目标

在 spec-010/011 基础上做 Agent 专项升级：补齐缺失工具、让 agent 能自建临时工具（代码执行 + 沙箱）、细分运行状态。

## 功能需求清单（FR-1 ~ FR-9，全部完成）

- FR-1：历史记录查询工具（搜索历史/创新点/综述/实验，只读）。
- FR-2：服务器增删改工具（危险 + 脱敏）。
- FR-3：SFTP 上传部署工具（危险）。
- FR-4：`run_python_code`（危险）。
- FR-5：`run_shell_command`（危险）。
- FR-6：每会话独立沙箱目录。
- FR-7：沙箱 subprocess + 超时 + 无密钥环境。
- FR-8：状态细分（thinking / executing:<tool> + 步骤）。
- FR-9：前端展示细分状态。

非功能：NFR-1 代码执行安全（目录隔离/超时/无密钥）；NFR-2 凭据安全。

## 验收结果

验收标准 AC-1 ~ AC-9 **全部 PASS**（轮次 1）。`pytest` 185 passed，前端 build 通过。

## 使用方式

- agent 现在可：回溯历史、管理服务器、SFTP 上传部署、写 Python/shell 代码在沙箱里执行（每会话隔离），运行状态细分展示「思考中 / 执行中：工具名（第 N 步）」。
- 沙箱为轻量 subprocess 隔离，抽象为可替换，后续可升级 Docker。

## 附带改动

- 前端路由从 state/localStorage 重构为 react-router-dom（`/search`、`/library`、`/history`、`/servers`、`/servers/:id`、`/agent`、`/settings`），刷新停留原页、支持前进后退/深链。
