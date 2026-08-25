# 实施计划：Agent 会话持久化与 UI 优化（spec-011）

## 任务拆分

1. 会话持久化：`agent_sessions` 表（迁移幂等）+ database CRUD。
2. 会话管理接口（列表/新建/重命名/删除）+ chat 持久化与自动标题。
3. 前端会话侧边栏（列表 + 新建/删除/重命名）。
4. Markdown 渲染（react-markdown + remark-gfm）。
5. 对话框 UI 优化（气泡 + 布局）。
6. 测试。

## 实施顺序

存储 → 会话接口 → 前端侧边栏 → Markdown → UI 优化 → 测试。

## 涉及文件/模块

- `backend/app/`（agent/sessions.py 改为 SQLite 存储，扩展 database/main/schemas）。
- `frontend/src/`（AgentPage 重构，新增会话侧边栏组件，扩展 api/types）。
- `tests/` 新增会话管理测试。

## 技术要点

- `agent_sessions` 表存 id/title/created_at/updated_at/messages(JSON)，用 `_migrate` 幂等建表。
- chat 时：加载 messages → 跑 agent 循环 → 保存 messages → 首次消息自动生成标题（截断前 N 字）。
- 会话列表接口不返回 messages（减小响应）。
- 前端：Agent 页改为左右布局（左会话列表，右对话区）；对话用气泡展示，agent 回复用 react-markdown 渲染。
- react-markdown + remark-gfm 加入 frontend 依赖（npm install）。

## 风险与应对

- Markdown XSS：react-markdown 默认不渲染原始 HTML。
- 会话 messages 可能较大：列表接口不含 messages。
