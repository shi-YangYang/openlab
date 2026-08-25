# 验收标准与验收记录：Agent 会话持久化与 UI 优化（spec-011）

## 验收标准

- AC-1（对应 FR-1）：会话持久化到 SQLite，重启后保留。
- AC-2（对应 FR-2）：会话列表展示（侧边栏，倒序，含标题与时间）。
- AC-3（对应 FR-3）：可新建会话。
- AC-4（对应 FR-4）：可删除会话（带确认）。
- AC-5（对应 FR-5）：会话标题自动生成 + 可手动重命名。
- AC-6（对应 FR-6）：LLM 回复 Markdown 正确渲染（标题/列表/代码块等）。
- AC-7（对应 FR-7）：对话框 UI 优化（侧边栏 + 气泡布局）。
- AC-8（对应 NFR-2）：Markdown 渲染不执行恶意 HTML（无 XSS）。

## 验收步骤

1. 启动后端与前端。
2. Agent 页新建会话、发消息，观察标题自动生成。
3. 刷新/重启后端，确认会话仍在。
4. 会话侧边栏列表、删除、重命名。
5. agent 回复含 Markdown 时正确渲染。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-25 | PASS | 无阻断问题。仅发现非阻断观察项：①前端构建存在单 chunk >500KB 告警（约 1.43MB，非本 Spec 引入的失败项）；②Windows 控制台中文输出乱码属终端编码显示问题，不影响数据正确性（断言均通过）。 | 通过，可进入下一环节 |

## 验收结论

PASS。AC-1~8 全部满足，无回归。

逐条判定与证据：

- **AC-1（会话持久化）PASS**：`agent_sessions` 表（`database.py:80-86`）通过 `_migrate` 幂等建表，`init_db` 连续执行 3 次无异常；`sessions.py` 读写走 SQLite（`save_messages`/`get_session`/`list_sessions`）。实测：写入后清空进程内 `_cache` 再读取，title 与 messages 仍在；直接用 sqlite3 独立连接确认 `agent_sessions` 表存在（`tests/test_agent_sessions.py::test_session_persists_across_restart` 亦覆盖）。
- **AC-2（会话列表）PASS**：`GET /api/agent/sessions` 返回不含 `messages` 的元数据（`database.list_agent_sessions` 仅取 id/title/created_at/updated_at，`ORDER BY updated_at DESC, id DESC`）。测试 `test_list_orders_by_updated_at_desc`、`test_list_excludes_messages` 通过；前端侧边栏展示标题与时间（`AgentPage.tsx:302-304`）。
- **AC-3（新建会话）PASS**：`POST /api/agent/sessions`（`main.py:748-752`）；前端「新建会话」按钮（`AgentPage.tsx:141-152`）。`test_session_crud_api` 通过。
- **AC-4（删除会话，带确认）PASS**：`DELETE /api/agent/sessions/{id}`（`main.py:771-775`）；前端 `Popconfirm` 确认（`AgentPage.tsx:294-299`）。`test_session_crud_api`、`test_delete_removes_persisted_row` 通过。
- **AC-5（自动标题 + 手动重命名）PASS**：`agent.py:100-105`、`209-211` 首条消息截断 30 字生成标题；`PUT /api/agent/sessions/{id}` 手动重命名。`test_chat_auto_generates_title`、`test_update_missing_session_returns_404` 通过；实测自动标题与手动重命名均生效。
- **AC-6（Markdown 渲染）PASS**：`AgentPage.tsx:359` 使用 `ReactMarkdown remarkPlugins={[remarkGfm]}`，支持标题/列表/代码块/表格（GFM）；`index.css` 有完整 `.markdown` 样式。
- **AC-7（UI 优化）PASS**：左右布局（左侧 240px 会话侧边栏 + 右侧对话区），用户/助手气泡式展示（`AgentPage.tsx:222-412`）。
- **AC-8（防 XSS）PASS**：未启用 `rehype-raw`，依赖树中无 `rehype-raw` 及任何 `rehype-*` 插件（`package-lock.json` 已核查），react-markdown 默认转义原始 HTML。

不回归判定：PASS。`pytest` 全量 160 passed（含 spec-010 的 agent 工具封装、手动循环、危险命令确认 approve/reject、密钥脱敏等原有用例）；`npm run build`（tsc + vite）通过。未发现 spec-010 功能退化。

测试实际运行情况：后端 `python -m pytest -q` → 160 passed in 4.57s；前端 `npm run build` → built in 5.35s（仅 chunk >500KB 体积告警，非错误）；独立 TestClient + FakeLLM 脚本验证 CRUD/持久化/自动标题/列表不含 messages/删除/重开连接读取全部通过。
