# Spec 025 实施计划

## 批次划分

### 批次 1：后端上传端点

- `main.py`：`POST /api/agent/sessions/{session_id}/attachments`
  - multipart：`file: UploadFile` + `path: str = Form("")`
  - 校验会话存在（`get_session_detail` 404）
  - `_safe_rel_path(path or file.filename)` → 写入 `settings.data_dir / "sandbox" / session_id / rel`
  - 返回 `{path, size}`
- 测试：`tests/test_agent_attachments.py`：正常上传、文件夹层级、无会话 404、路径穿越拒绝。

### 批次 2：前端

- `AgentPage.tsx`：
  - 输入区左下角（模型 Select 左边）加「+」按钮（PlusOutlined）→ Popover 菜单（添加文件/添加文件夹，用隐藏 input[type=file] 与 input[webkitdirectory]）。
  - 上传：逐文件 POST multipart（fetch FormData），进度用 uploading state + Spin。
  - 已上传文件 Tag 列表（输入框上方）。
  - 全部完成后自动 `channel.sendChat` 一条系统提示消息。
- `api.ts`：`uploadAttachment(sessionId, file, path)` 封装。

## 验证方式

`pytest tests -q`；`npm run build`；手工冒烟见 acceptance.md。
