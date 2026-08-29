# Spec：Agent 附件功能（spec-025）

## 元信息

- **Spec 编号**：`spec-025-agent-attachments`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-agent-attachments.md`
- **负责人**：协调开发 Agent

## 背景与动机

用户需要给 Agent 提供本地文件/文件夹作为工作上下文（代码库、数据文件等）。当前 Agent 只能访问自己的会话沙箱，没有入口把本地文件送进去。

## 目标

- Agent 输入框左下角新增「+」按钮，弹出菜单选择「添加文件 / 添加文件夹」。
- 文件上传到当前会话沙箱目录，Agent 后续对话可直接读写。
- 上传完成自动通知 Agent（消息形式），并展示已上传列表。

## 范围

### 包含（In Scope）

- 后端附件上传 REST 端点（multipart，支持多文件 + 相对路径）。
- 前端「+」菜单（文件/文件夹选择器）、上传状态、已上传文件列表。
- 上传完成后自动发一条提示消息给 Agent。

### 不包含（Out of Scope）

- zip 压缩包自动解压。
- 附件删除/管理 UI（沙箱清理跟随会话删除）。
- 图片粘贴/截图上传（后续菜单预留）。

## 需求描述

### 功能需求

- FR-1：后端新增 `POST /api/agent/sessions/{session_id}/attachments`（multipart）：
  - 字段 `file`（UploadFile）+ `path`（相对路径，文件夹上传时含目录层级）。
  - 文件写入 `data/sandbox/{session_id}/{path}`；路径经 `_safe_rel_path` 校验（防穿越）。
  - 无会话时 400「请先发送消息创建会话」；文件名冲突直接覆盖（沙箱内幂等）。
- FR-2：前端「+」按钮（输入框左下角，模型选择器左边）：
  - 点击弹 Popover 菜单：「添加文件」「添加文件夹」（后续预留分隔线 + 更多入口）。
  - 添加文件：`<input type="file" multiple>`；添加文件夹：`<input webkitdirectory>`（取 `webkitRelativePath` 作为相对路径）。
  - 上传中按钮显示 Spin；完成后 `message.success` 列出路径。
- FR-3：全部文件上传完成后，自动向 Agent 发送一条用户消息：`[用户上传了以下文件到沙箱]\n- path1\n- path2\n请留意这些文件。`，使 Agent 在上下文中感知文件存在。
- FR-4：已上传文件列表显示在输入框上方（Tag 列表，Tag 内容为相对路径），供用户确认。

### 非功能需求

- NFR-1：上传路径安全校验（`_safe_rel_path` 防路径穿越），复用 main.py 已有函数。
- NFR-2：上传端点不做大小硬限制（本地自用），但记录文件大小到响应。
- NFR-3：会话删除时沙箱整体清理（既有逻辑），附件自动清理。
- NFR-4：`pytest tests -q` 与 `npm run build` 通过。

## 数据结构约定

- 附件落盘路径：`data/sandbox/{session_id}/{relative_path}`（与 spec-012 沙箱一致）。
- 无新增数据库表（附件即沙箱文件，无需单独索引）。

## 后端接口草案

- `POST /api/agent/sessions/{session_id}/attachments` — 上传附件（multipart: file + path）

## 依赖与前置条件

- spec-010/011（沙箱与会话）、spec-020（AgentPage WS 通道）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- webkitdirectory 在 Firefox 支持有限（Chrome/Edge 完整），不影响主流程。
- 大文件夹上传逐文件串行较慢——首版可接受，后续可并发。
