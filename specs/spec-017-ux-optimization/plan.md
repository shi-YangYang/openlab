# Spec 017 实施计划

## 概览

本次为纯前端改造，分 4 个批次：服务器详情折叠、分析页、其余三个功能页、入口与标题。每批完成可独立验证。

## 批次划分

### 批次 1：服务器详情折叠

- `frontend/src/components/ServerDetailPage.tsx`：
  - 用 AntD `Collapse` 包裹四个区块（监控/部署/环境配置/终端），`defaultActiveKey={[]}`（默认全折叠）。
  - 保留各区块现有实现（`MonitorSection`/`DeploySection`/`ExecSection`/`TerminalView`），仅改为 `Collapse` 的 `items`。

### 批次 2：论文分析页

- 新建 `frontend/src/components/PaperAnalysisPage.tsx`：
  - 由 `AnalysisModal.tsx` 改造：去掉 `Modal` 外壳，改为页面布局（顶部 `Breadcrumb` + `Card`）。
  - 从路由参数读 `arxivId`；用 `listPapers([arxivId])` 查询标题，回退显示 arxivId。
  - 保留语言选择、分析、导出、轮询、结果展示逻辑与 cleanup。
- `frontend/src/api.ts`：确认 `listPapers` 已支持按 id 查询（已存在）。

### 批次 3：对比综述 / 创新点 / 实验方案页

- 新建 `frontend/src/components/ReviewPage.tsx`（由 `ReviewModal.tsx` 改造）。
- 新建 `frontend/src/components/InnovationPage.tsx`（由 `InnovationModal.tsx` 改造）。
- 新建 `frontend/src/components/ExperimentPage.tsx`（由 `ExperimentModal.tsx` 改造）：
  - 支持 `?ids=`（sourceType=papers）与 `?innovation_id=`（sourceType=innovation）。
- 三个页面均：从 URL query 解析入参、去掉 `Modal` 外壳、加 `Breadcrumb`、保留原逻辑与 cleanup。
- 面包屑：论文相关第一段「论文库」链接 `/library`；实验方案（来源创新点）第一段「创新点历史」链接 `/history/innovation`。

### 批次 4：入口改造 + 路由 + 标题

- `frontend/src/App.tsx`：
  - 新增路由 `/papers/:arxivId/analysis`、`/papers/review`、`/papers/innovation`、`/papers/experiment`。
  - 删除 `openAnalyze/openReview/openInnovation/openExperiment` 及对应 Modal 渲染与 state，改为 `navigate(...)`。
  - `selectedKey` 逻辑：`/papers/...` 无需高亮顶级菜单（或归入不匹配项，保持现状即可）。
- `frontend/src/components/PaperTable.tsx`：`onAnalyze` 由回调改为 `navigate`（或保持回调，由上层改为导航，二选一，见下）。
- `frontend/src/components/PaperWorkspace.tsx` / `hooks/usePaperWorkspace.ts`：`handleOpenReview/handleOpenInnovation/handleOpenExperiment` 改为导航到对应路由（保留「至少 1/2 篇」校验）。
- `frontend/src/components/InnovationHistoryList.tsx`：「实验方案」按钮改为导航 `/papers/experiment?innovation_id={id}`。
- `frontend/index.html`：`<title>` 改为 `openlab科研agent`。
- 删除不再使用的 4 个 Modal 组件文件。

> 说明：`PaperTable` 的「分析」按钮当前通过 `onAnalyze` 回调层层上抛；为最小改动，可保留回调、由 `App.tsx` 将 `onAnalyzeOne` 实现改为 `navigate`。实施时据此选择改动最小的方案。

## 文件清单

### 前端
- `frontend/index.html`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`（如需辅助函数解析 query）
- `frontend/src/components/ServerDetailPage.tsx`
- `frontend/src/components/PaperTable.tsx`（或保持）
- `frontend/src/components/PaperWorkspace.tsx`
- `frontend/src/hooks/usePaperWorkspace.ts`
- `frontend/src/components/InnovationHistoryList.tsx`
- 新建：`PaperAnalysisPage.tsx`、`ReviewPage.tsx`、`InnovationPage.tsx`、`ExperimentPage.tsx`
- 删除：`AnalysisModal.tsx`、`ReviewModal.tsx`、`InnovationModal.tsx`、`ExperimentModal.tsx`

### 后端
- 无改动。

### 测试
- 无后端测试改动；前端以 `npm run build` + 手工冒烟验证。

## 验证方式

- 前端：`npm run build`。
- 后端回归：`pytest tests -q`（确认无影响）。
- 手工冒烟：按 acceptance.md 逐项验证。
