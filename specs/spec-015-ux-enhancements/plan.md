# Spec 015 实施计划

## 概览

本次改动横跨前端（布局/导航/表单/删除）与后端（实验方案 API、LLM 配置扩展、删除、上传 URL）。按依赖顺序分 6 个批次实施，每批完成即可独立验证。

## 批次划分

### 批次 1：内容区宽度 + 历史菜单二级化

- `frontend/src/App.tsx`：
  - `Content` 改为响应式：`maxWidth: 1600, width: '100%', margin: '0 auto', padding: 24`（视口 < 1600 时自动收缩，保留内边距）。
  - `MENU_ITEMS` 中「历史」改为带 `children` 的二级菜单，三个子项 key 分别为 `history/search`、`history/innovation`、`history/experiment`。
  - 删除 `historyPage` 的 Tabs 结构，改为三个独立 Route。
  - 路由新增 `/history/search`、`history/innovation`、`history/experiment`，旧 `/history` 重定向到 `/history/search`。
  - `selectedKey` 逻辑适配多级 key（取完整 path）。
- 后端无改动。

### 批次 2：实验方案历史 API（后端）

- `backend/app/schemas.py`：新增 `ExperimentHistoryItem`（含 source_label/plan_count 等列表友好字段，或直接复用 `ExperimentRecord` 去掉 content）。
- `backend/app/main.py`：
  - `GET /api/experiments`：返回实验方案列表（不含完整 content，或含但截断）。
  - `DELETE /api/experiments/{experiment_id}`。
  - `DELETE /api/experiments`。
- `backend/app/database.py`：
  - `delete_experiment(experiment_id)`、`clear_experiments()`。
- 复用已有 `list_experiments()`。

### 批次 3：实验方案历史列表页（前端）

- `frontend/src/components/ExperimentHistoryList.tsx`：新建，参考 `InnovationHistoryList` 的结构。
  - 列表列：时间 / 来源（论文 or 创新点#）/ 语言 / 状态 / 方案数 / 操作（查看、导出、删除）。
  - 查看弹窗：复用 ExperimentModal 的内容渲染（可抽出共享组件，或简化展示）。
  - 导出：复用 `exportExperimentMarkdown`。
  - 删除：`deleteExperiment` + Popconfirm。
- `frontend/src/api.ts`：新增 `listExperiments`、`deleteExperiment`、`clearExperiments`。
- `frontend/src/types.ts`：新增 `ExperimentHistoryItem` 类型。

### 批次 4：LLM 配置增强

- 后端：
  - `backend/app/llm_config.py`：`_VALID_KEYS` 增加 `reasoning_effort`；`save_config`/`load_config`/`get_effective_config` 支持该字段。
  - `backend/app/schemas.py`：`LLMConfig`、`LLMConfigUpdate` 增加 `reasoning_effort: Optional[str]`；新增 `LLMModelsRequest`（base_url/api_key）、`LLMModelsResponse`（models: List[str]）。
  - `backend/app/main.py`：新增 `POST /api/llm/models`。
  - 各 LLM 调用点（`analysis.py`、`upload.py`、`review`/`innovation`/`experiment` 的 `_chat` 或等价处）：在创建 `ChatOpenAI` 时，若 `reasoning_effort` 非空则传入。
- 前端：
  - `LlmConfigForm.tsx`：新增「思考强度」下拉（low/medium/high，可清空）；新增「获取模型」按钮，调用 `/api/llm/models` 后填充模型下拉；模型字段改为 `Select`（可搜索 + 可自定义 tags）。
  - `api.ts`、`types.ts` 补类型与接口。

### 批次 5：论文库删除

- 后端：
  - `backend/app/database.py`：`delete_paper(arxiv_id)`（删 papers + analyses，返回是否删除）。
  - `backend/app/main.py`：`DELETE /api/papers/{arxiv_id}`，删除本地 PDF（路径白名单校验），幂等。
- 前端：
  - `PaperTable.tsx` 的 `paperActionColumn` 增加「删除」按钮（Popconfirm），通过回调触发。
  - `usePaperWorkspace.ts` 增加 `handleDeleteOne`。
  - `api.ts` 增加 `deletePaper`。
  - 仅论文库（library）场景展示删除按钮；搜索页不展示。

### 批次 6：上传 PDF 分析来源 URL

- 后端：
  - `backend/app/upload.py`：`_SYSTEM_PROMPT` 增加 `url` 键；`extract_metadata` 返回含 `url` 的 dict。
  - `backend/app/schemas.py`：`PaperMetadata` 增加 `url: str = ""`；`UploadConfirmRequest` 透传。
  - `backend/app/main.py`：`confirm_paper_pdf` 入库时写入 `url`。
- 前端：
  - `UploadPdfModal.tsx`：确认表单新增「来源 URL」输入项，预填分析结果。
  - `types.ts`：`PaperMetadata` 增加 `url`。
  - `PaperTable.tsx`：upload 来源论文标题链接/查看原文使用 `r.url`（已有非 arxiv 逻辑，确认 upload 走该分支）。

## 文件清单

### 后端
- `backend/app/llm_config.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/upload.py`
- `backend/app/analysis.py`（透传 reasoning_effort）
- `backend/app/experiment.py`（透传 reasoning_effort）
- `backend/app/innovation.py`（透传 reasoning_effort，若共用 _chat）

### 前端
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/components/LlmConfigForm.tsx`
- `frontend/src/components/PaperTable.tsx`
- `frontend/src/components/UploadPdfModal.tsx`
- `frontend/src/components/ExperimentHistoryList.tsx`（新建）
- `frontend/src/hooks/usePaperWorkspace.ts`

### 测试
- `tests/test_api.py`：删除论文、实验方案列表/删除、LLM models 接口。
- `tests/test_upload.py`：url 字段。
- `tests/test_llm_config.py`：reasoning_effort 持久化。
- `tests/test_database.py`：delete_paper。

## 验证方式

- 后端：`pytest tests -q`。
- 前端：`npm run build`。
- 手工冒烟：按 acceptance.md 逐项验证。
