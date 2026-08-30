# Summary：spec-030-agent-message-toolbar

## 完成日期

2026-08-30

## 实施内容

Agent 聊天区域消息悬浮 toolbar：悬浮任意消息时，气泡下方淡入「模型名 → 时间 → 复制」三项信息栏。

### 前端（4 文件）

- `AgentChatMessages.tsx`：新增 `renderToolbar`（模型名纯文本，超长 180px 省略号 + Tooltip 全名；时间 `YYYY-MM-DD HH:mm` 纯文本；复制为纯 icon CopyOutlined + tooltip「复制」，复制原始 Markdown 文本）；删除气泡左/右侧旧「复制原文」悬浮按钮与气泡内时间小字；消息间距 `Space size 12 → 32`。
- `AgentPage.module.css`：新增 `.turnToolbar`（absolute `top:100%`、flex gap 10px、默认 opacity 0 + `pointer-events:none`、行 hover 0.2s 淡入）及对齐/截断样式；删除 `.turnCopy/.copyLeft/.copyRight/.bubbleTime/.assistantTime`。
- `useAgentState.ts`：`hhmmNow()` → `timestampNow()`（完整 `YYYY-MM-DD HH:mm`）；新增 `activeModelRef` 记录发送时刻生效模型（`model || groupDefaults.model`），用户/AI turn 均记录 time + model；历史加载映射后端 `time`/`model`（null 回退本地值，UI 层 `-` 兜底）。
- `types.ts`：`AgentSessionMessage` 增加 `time?/model?`。

### 后端（2 文件）

- `agent/agent.py`：新增 `_stamp_message()`，向用户/AI 消息 `additional_kwargs` 写入 `ts`（`%Y-%m-%d %H:%M:%S`）与 `model`（用户消息 = 请求生效模型；AI 消息 = `effective_model`，与 `build_llm` 同源），覆盖 run_chat 与 run_approve 路径。
- `agent/sessions.py`：`normalize_history` 返回项扩展 `time`（`ts[:16]`）与 `model`，缺失/畸形 kwargs 容错返回 `None`（兼容旧会话与压缩摘要消息）。

## 验证结果

- 后端 pytest 全量 **292 passed**；前端 `npm run build`（tsc + vite）通过。
- 验收 Agent 独立核实：FR-1~FR-12 逐条 PASS；AC-1~AC-11 全部 PASS 或 CODE-REVIEW-PASS（UI 悬浮/剪贴板/重载类项按代码推演）；逻辑抽查脚本验证旧消息容错、ts 截取、kwargs 保留。
- 无超范围改动、无密钥泄露、无调试残留。

## 遗留事项

- `tests/` 无 `normalize_history` 新增字段的专项测试（验收备注的可选增强，不阻塞）。
- AC-1/3/5/7/8/11 属 UI 手动验证项，建议用户实际运行体验确认。

## 返工记录（2026-08-30，用户实测发现）

- **缺陷**：切换会话/重启后 toolbar 的模型名与时间全部显示 `-`。
- **根因**：`AgentSessionMessage`（Pydantic）只有 `role`/`content`，路由 `response_model=AgentSessionDetail` 在响应序列化时过滤掉 `normalize_history` 返回的 `time`/`model`——持久化与函数层均正常，唯独 HTTP 响应边界丢字段；实施与验收均未覆盖该层。
- **修复**：`schemas.py` 的 `AgentSessionMessage` 增加 `time`/`model` 可选字段；新增回归测试 `test_session_detail_returns_time_and_model`（TestClient 走完整 HTTP 路径断言两字段）。
- **验证**：pytest 全量 293 passed。
