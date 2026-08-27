# Spec 024 实施计划

## 批次划分

### 批次 1：Bug 类（B-1~B-4）

- **B-1** `ExperimentRunPanel.tsx`：`open` 且无内存 runId 时调 `listExperimentRuns()` 过滤 `experiment_id===experiment.id && status in (preparing/running/paused)` → 命中则 `setRunId(latest.id)` + `setRunStatus(latest.status)` + `connectWs` + 拉日志尾渲染。
- **B-2** `main.py delete_agent_session`：删除前调 agent ws 的 runner stop（导入 AgentRunner 单例）；`agent/ws.py` 若无全局单例则导出一个。
- **B-3** `main.py delete_experiment`：先查 `database.list_experiment_runs()` 过滤 experiment_id，逐个 stop + delete（含日志）。
- **B-4** `usePaperWorkspace.ts`：deadline 180000→600000；超时循环退出后追加一次 `listPapers(ids)` 校准。

### 批次 2：体验类（U-1~U-5）

- **U-1** `ExperimentRunPanel.tsx`：ws `onclose` 后若 run 状态仍活跃 → 指数退避重连 ≤5 次；重连成功拉 `getExperimentRun` 恢复 status/stepStates/log_tail；断线期间日志区上方 Alert。
- **U-2** 同 B-4（合并实现）。
- **U-3** 日志区头部加「复制日志」「下载日志」小按钮（复制 filteredLogs join；下载 .log blob）。
- **U-4** `AgentPage.tsx` 会话删除 Popconfirm：`item.running` 时 title 改「该会话正在运行，删除将终止任务并删除记录？」。
- **U-5** `AgentPage.tsx` 输入区下方控件行加 `flexWrap`、圆环外层 `flexShrink:0`。

### 批次 3：工程类（E-1~E-3）与 ErrorBoundary 测试

- **E-1** `database.py _connect`：`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`
- **E-2** `_migrate`：`CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source)`、`idx_papers_status ON papers(status)`。
- **E-3** 新建 `frontend/src/components/ErrorBoundary.tsx`（class 组件 componentDidCatch），`main.tsx` 包裹 `<App/>`；崩溃时显示错误摘要 + 重新加载按钮。
- 测试：E-1/E-2 由既有 db 测试回归覆盖；E-3 无自动化（React 测试基建缺失），手工验证。

## 文件清单

- 前端：`ExperimentRunPanel.tsx`、`AgentPage.tsx`、`usePaperWorkspace.ts`、`ErrorBoundary.tsx`（新）、`main.tsx`
- 后端：`main.py`、`database.py`、`agent/ws.py`（如需导出单例）

## 验证方式

`pytest tests -q`、`npm run build`、按 acceptance.md 冒烟。
