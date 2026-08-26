# Spec 018 实施计划

## 概览

横跨后端（LLM 配置组化 + agent token 统计/模型覆盖）与前端（设置页组管理 + agent 页选择/展示）。分 4 个批次，每批可独立验证。

## 批次划分

### 批次 1：后端 LLM 配置组化

- `backend/app/llm_config.py` 重构：
  - 新结构 `{ active_group, groups: [...] }`；`_VALID_KEYS` 改为组字段。
  - `_migrate`：检测旧扁平结构自动转为单组 `default`。
  - 新增 `list_groups()`、`get_group(id)`、`save_config(data)`（整体保存）、`get_effective_config()`（返回当前组默认模型/强度）。
  - 保留 env/内置默认回落。
- `backend/app/schemas.py`：新增 `LLMGroup`、`LLMConfigResponse`（active_group + groups）；移除/改造旧 `LLMConfig`/`LLMConfigUpdate` 为组结构；保留 `LLMModelsRequest/Response`、`LLMTestRequest/Response`。
- `backend/app/main.py`：
  - `GET /api/llm/config` 返回 `{active_group, groups}`；`PUT /api/llm/config` 整体保存。
  - 校验：`active_group` 必须存在于 groups；组 `id` 非空且不重复；`default_model` 缺省取 `models[0]`。
- 回归确认：`analysis.py`/`innovation.py`/`experiment.py`/`upload.py`/`llm.py`/`agent/agent.py` 仍通过 `get_effective_config()` 工作（无需改动，除非需要模型覆盖）。

### 批次 2：后端 agent token 统计与模型/强度覆盖

- `backend/app/database.py`：`agent_sessions` 表新增 `input_tokens`、`output_tokens`（`_migrate` 补列）；新增 `add_agent_session_usage(session_id, input_tokens, output_tokens)`、并在读取时返回。
- `backend/app/agent/sessions.py`：`get_session_detail` 返回 `usage`；`save_messages` 逻辑不变。
- `backend/app/agent/agent.py`：
  - `build_llm(model=None, reasoning_effort=None)` 接受覆盖。
  - `_run_loop` 中每次 `llm.ainvoke` 后读取 `response.usage_metadata`，累计并 `add_agent_session_usage`。
  - `run_chat`/`run_approve` 接收并传递 `model`/`reasoning_effort`（approve 需与 pending 保持一致，实现时存 pending 或前端携带）。
- `backend/app/main.py`：`agent/chat`、`agent/approve` 请求体新增 `model?`/`reasoning_effort?`；`get_session_detail` 返回 usage。
- `backend/app/schemas.py`：`AgentChatRequest`/`AgentApproveRequest` 增加可选字段；`AgentSessionDetail` 增加 `usage`。

### 批次 3：前端设置页配置组管理

- `frontend/src/types.ts`：新增 `LlmGroup`、`LlmGroupsConfig`；调整 `LlmConfig` 相关类型。
- `frontend/src/api.ts`：`getLlmConfig` 返回 `{active_group, groups}`；`saveLlmConfig` 整体保存；复用 `getLlmModels`/`testLlmConnection`/`getLlmPresets`。
- `frontend/src/components/LlmConfigForm.tsx` 重构：
  - 配置组列表 + 当前组标记 + 新增/编辑/删除。
  - 每组表单：name、base_url、api_key、models（tags 多选/自定义）、default_model（从 models 选或输入）、reasoning_effort（AutoComplete）。
  - 每组「获取模型」「连通性测试」按钮。
  - 保存整体 `PUT /api/llm/config`。

### 批次 4：前端 agent 页选择与上下文展示

- `frontend/src/types.ts` / `api.ts`：`agentChat`/`agentApprove` 增加可选 model/reasoning_effort；`AgentSessionDetail` 增加 usage。
- `frontend/src/components/AgentPage.tsx`：
  - 顶部加「模型」下拉（当前组 models，默认 default_model）与「思考强度」下拉。
  - 加载时读取当前组配置（`getLlmConfig` 的 active_group → groups 找当前组），填充下拉。
  - 发送/确认时把 model/reasoning_effort 传给 `agentChat`/`agentApprove`。
  - 展示上下文使用（session detail 的 `usage`，如「输入 X / 输出 Y tokens」），随会话刷新。

## 文件清单

### 后端
- `backend/app/llm_config.py`
- `backend/app/schemas.py`
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/agent/agent.py`
- `backend/app/agent/sessions.py`

### 前端
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/components/LlmConfigForm.tsx`
- `frontend/src/components/AgentPage.tsx`

### 测试
- `tests/test_llm_config.py`：组结构、迁移、有效配置、active_group 校验。
- `tests/test_database.py`：agent_sessions token 列与累加。
- `tests/test_api.py`：`GET/PUT /api/llm/config`、agent chat/approve 携带模型强度、session detail usage。
- `tests/test_agent.py` / `test_agent_sessions.py`：usage 统计、模型覆盖。

## 验证方式

- 后端：`pytest tests -q`。
- 前端：`npm run build`。
- 手工冒烟：按 acceptance.md 逐项验证。
