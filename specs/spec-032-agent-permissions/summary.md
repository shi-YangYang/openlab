# Summary：spec-032-agent-permissions

## 完成日期

2026-08-30

## 实施内容

Agent 权限管理系统：Codex 式三级全局模式 + 安全底线 + 会话级放行。

### 后端（6 文件）

- `agent/permissions.py`（新建）：权限引擎——`FORBIDDEN_TOOLS={"delete_server"}`、15 条破坏性命令黑名单、24 条默认只读白名单、`evaluate()` 六层优先级（黑名单工具→黑名单命令→full→会话放行→standard 规则→ask）；`data/agent_permissions.json` 持久化（损坏回退默认并重建——实施中发现并修复 `load()` 未初始化变量 bug）；含 `;`/`&&`/`||`/`|` 的复合命令不吃白名单（防绕过）。
- `agent/agent.py`：执行门控改为 `evaluate()`（22 个安全工具路径不变）；`run_approve` 支持 `scope`（once 缺省兼容 / session 加入会话放行集）。
- `agent/sessions.py`：`Session.allowed_tools` 内存放行集（重启/新会话失效）。
- `agent/ws.py` + `routes/agent.py` + `schemas.py`：approve 透传 scope；`GET/PUT /api/agent/permissions`、`POST reset`（PUT 校验非法 mode 400、白名单去杂）。

### 前端（8 文件）

- `usePermissions.ts`（新建）：模块级单例 store（useSyncExternalStore），设置页与工具栏同一数据源实时同步；失败不静默改配置。
- `AgentPermissionSelect.tsx`（新建）：工具栏 antd Select 三模式下拉；**full 激活橙色警示**（#fa8c16）；切 full 弹风险确认。
- `AgentPermissionSettings.tsx`（新建）+ `App.tsx`：设置页「Agent 权限」卡片（三模式 Radio + 白名单 Tag 编辑 + 恢复默认，即时保存）。
- `AgentApprovalModal.tsx`：三按钮（允许一次/本会话允许/拒绝）+「切换完全访问」提示。
- `useAgentChannel.ts`/`useAgentState.ts`：approve scope 透传（缺省 once）。

## 验证结果

- pytest 全量 **369 passed**（既有 293 + 新增 76：评估矩阵/会话放行隔离/损坏回退/API/scope 集成）。
- `npm run build` 通过；端到端抽查 **11/11**（TestClient + mock LLM：standard 白名单免审批、`rm -rf /` 必 pending、scope=session 放行、full 下黑名单仍 pending、GET/PUT/reset 实测）。
- 验收独立核对 FR-1~FR-17 全满足；AC-1~13 全 PASS / CODE-REVIEW-PASS；无超范围改动、无密钥泄露、无调试残留。

## 已知低优先级遗留（验收记录，不阻塞）

1. scope=session 会将黑名单工具名也写入放行集（死条目，fail-closed 无风险，可后续跳过）。
2. 工具栏下拉框加载失败时无限 loading 无错误提示。
3. pending_approval 不带黑名单标记，弹窗对黑名单命令展示的三按钮部分冗余（后端强制兜底，按钮 title 已注明）。
4. 白名单匹配区分大小写、黑名单不区分（实施自洽，spec 未规定）。
5. `resetWhitelist` 经 reset→re-PUT 双请求实现（非原子，失败窗口极小）。

## 遗留事项

- 建议用户实际运行体验三模式切换与审批弹窗。
