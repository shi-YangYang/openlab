# spec-025 Agent 附件（文件/文件夹）决策

## 决策标题

确定 Agent 页附件（文件/文件夹）上传的实现方式与 Agent 侧的文件使用机制。

## 元信息

- **日期**：2026-08-28
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-025-agent-attachments

## 背景与问题

用户希望给 Agent 提供本地文件/文件夹作为上下文（如让 Agent 分析一份代码库、处理一份数据文件）。当前 Agent 只能访问自己的会话沙箱（`data/sandbox/{session_id}`），没有入口把本地文件送进去。

## 备选方案

- 方案 A：文件直接 base64 塞进 chat 消息体 —— 消息体膨胀，大文件不可行。
- 方案 B（采用）：REST 独立上传端点把文件写入**当前会话的沙箱目录**，Agent 的 `run_python`/`run_shell` 天然能在沙箱里读到；前端输入框左下角「+」弹出菜单选择文件/文件夹。

## 决策

1. **上传端点**：`POST /api/agent/sessions/{session_id}/attachments`（multipart，`paths` 字段携带相对路径支持文件夹结构），文件写入 `data/sandbox/{session_id}/` 下（保持相对路径层级）。无 session_id 时返回 400（先发一条消息创建会话）。
2. **文件夹上传**：前端用 `<input webkitdirectory>` 采集 File 对象的 `webkitRelativePath`，逐个调上传端点（multipart 一次一个文件，路径字段保留目录层级）。不加 zip 解压（保持简单）。
3. **Agent 感知**：上传完成后前端自动向 Agent 发一条系统级提示消息（如"[用户上传了文件: a.py, b.csv 到沙箱]"），Agent 即可在后续对话中用沙箱工具读取。不新增专用 agent 工具——沙箱 shell/python 已覆盖读写。
4. **前端 UI**：输入框左下角「+」按钮（PlusOutlined），点击弹出 Popover 菜单，菜单项：「添加文件」（`<input type=file multiple>`）、「添加文件夹」（`<input webkitdirectory>`）；后续功能（如截图、连接数据源）预留菜单位。上传中显示 Spin + 文件名，完成后 message.success 列出已上传路径。

## 理由

- 沙箱目录是 Agent 工具的天然工作区，文件放进去后零额外集成成本。
- REST 上传（非 WS base64）避免消息协议膨胀，复用 FastAPI 原生 multipart。
- 不新增 agent 工具：沙箱 shell `cat a.py` 就能读文件，符合"工具最小集"原则。

## 影响与后果

- 后端新增一个 REST 端点 + 上传路径安全校验（复用 `_safe_rel_path`）。
- 前端 AgentPage 输入区新增「+」菜单与上传状态展示。
- 沙箱目录在会话删除时已有清理逻辑（spec-012），附件随之清理，无额外工作。
