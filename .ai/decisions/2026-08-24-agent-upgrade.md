# spec-012 Agent 专项升级决策

## 决策标题

确定 Agent 专项升级（spec-012）的工具补齐、动态工具/沙箱与状态细分方案。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户（沙箱由协调开发 Agent 推荐）
- **关联 Spec**：spec-012-agent-upgrade

## 决策

1. **补齐工具**：历史记录查询（只读）+ 服务器增删改（危险）+ SFTP 上传部署（危险）。
2. **动态工具**：Python 代码执行 + 本地 shell 命令执行，两者都要。
3. **沙箱**：轻量子进程沙箱——每会话独立工作目录 + subprocess + 超时 + 剥离密钥的环境变量。
4. **状态细分**：思考中 / 执行中（含工具名）+ 步骤计数，持久化并前端轮询。

## 理由

- 历史查询让 agent 能回溯；服务器 CRUD 与 SFTP 上传补齐部署能力。
- Python 代码执行是「临时工具」的核心（agent 写代码即造工具），本地 shell 补充系统操作。
- 轻量子进程沙箱在安全与复杂度间取平衡，适合个人本地工具。
- 细分状态提升长任务的可观测性。

## 影响与后果

- 新增约 10 个工具 + 沙箱模块 + 状态字段。
- agent_sessions 表 `running` 升级为 `status`（thinking/executing:<tool>/idle）。
- 新增 subprocess 沙箱执行模块（`backend/app/agent/sandbox.py`）。
