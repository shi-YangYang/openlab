# Spec 022 实施计划

## 概览

三批：论文库与上传（批次1）、agent 页交互（批次2）、历史页过滤与分页（批次3）。

## 批次划分

### 批次 1：论文库与上传（FR-1 / FR-2 / FR-5）

- `frontend/src/components/PaperTable.tsx`：
  - `paperActionColumn` 的「分析」按钮按 statusMap 判定禁用；`<Tooltip title="请先下载该论文">` 包裹。注意 statusMap 可能缺 key（如详情页来源表），缺失时视为不可下载，同样禁用。
  - 分页 props 改为可调。
- 后端 `backend/app/upload.py` + `main.py confirm_paper_pdf`：confirm 时查 papers 表是否已有同 source='upload' 且 title 相似的记录（title 精确匹配即可），命中则响应带 `duplicate_of`。
- `backend/app/schemas.py`：confirm 响应模型加字段。
- 前端 `UploadPdfModal.tsx`：保存成功后若 duplicate_of 存在则 message.warning。

### 批次 2：Agent 页（FR-3 / FR-4 / FR-6 / FR-7 / FR-8 / FR-9 部分）

- `LlmConfigForm.tsx` handleSave 成功后 `localStorage.setItem('openlab.llm.updated', Date.now())`。
- `AgentPage.tsx`：
  - useEffect 监听 window 'storage' 事件刷新配置（同时兼容同页：在 LlmConfigForm 直接写 localStorage 不触发本页 storage——由两页不同路由、实际跨页操作的场景覆盖；补一个自定义事件 'openlab:llm-updated' 同页兜底，App 内两个组件通过 window.dispatchEvent 触发）。
  - Turn 加 time；发消息与 done/stopped 时写入 HH:mm。
  - 会话列表 interrupted Tag。
  - 工具 Collapse defaultActiveKey 动态计算失败项。
  - 审批 Modal：command 提取展示 + JSON 折叠。
- `api.ts`/`types.ts` 同步 duplicate_of。

### 批次 3：重试与历史过滤（FR-9 / FR-10）

- `PaperAnalysisPage.tsx`：failed Alert 增加「重试分析」（loading 态复用 analyzing）。
- `ReviewPage.tsx`：failed Alert 增加「重试综述」。
- `SearchHistoryList.tsx` / `ExperimentHistoryList.tsx`：头部加 Input.Search 过滤（参考 InnovationHistoryList 关键词过滤实现）。

## 文件清单

### 前端
- `components/PaperTable.tsx`
- `components/LlmConfigForm.tsx`
- `components/AgentPage.tsx`
- `components/PaperAnalysisPage.tsx`
- `components/ReviewPage.tsx`
- `components/SearchHistoryList.tsx`
- `components/ExperimentHistoryList.tsx`
- `components/UploadPdfModal.tsx`
- `api.ts`、`types.ts`

### 后端
- `app/upload.py`、`app/main.py`、`app/schemas.py`

## 验证方式

- 后端 `pytest tests -q`；前端 `npm run build`；手工冒烟见 acceptance.md。
