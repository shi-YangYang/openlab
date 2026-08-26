# Spec 019 实施计划

## 概览

横跨后端（模型条目结构升级 + `/models` 元数据 + token 统计细化）与前端（模型列表 UI + 百分比展示）。分 4 个批次，每批可独立验证。

## 批次划分

### 批次 1：后端模型条目结构与迁移

- `backend/app/llm_config.py`：
  - 组内 `models` 改为对象数组 `[{id, context_length, reasoning_efforts}]`。
  - `_migrate`：旧字符串条目转对象；组级 `reasoning_effort` 下沉到默认模型条目后移除；旧单值 reasoning_effort 转单元素列表。
  - `get_effective_config()` 的 `reasoning_effort` 取自默认模型条目的 `reasoning_efforts` 首项。
  - `save_config` 校验与 `default_model` 逻辑适配（default_model 缺省取第一个模型 id）。
- `backend/app/schemas.py`：新增 `LLMModelInfo`（id/context_length/reasoning_efforts）；`LLMGroup.models` 类型改 `List[LLMModelInfo]`。

### 批次 2：后端 /models 元数据 + token 统计细化

- `backend/app/main.py`：`/api/llm/models` 返回 `List[LLMModelInfo]`，尽力解析平台返回的上下文长度字段（`max_context_length`/`context_length`/`context_window`/`max_tokens` 等）与思考强度选项字段（`reasoning_efforts`/`supported_reasoning_efforts` 等，读不到按空列表），读不到置 null/空。
- `backend/app/database.py`：`agent_sessions` 新增 `last_input_tokens`、`last_output_tokens`（`_migrate` 补列）；新增记录函数。
- `backend/app/agent/agent.py`：`_run_loop` 每次调用后同时更新累计与「最近一次」token。
- `backend/app/agent/sessions.py`：`get_session_detail` 的 usage 增加 `last_input_tokens`/`last_output_tokens`。
- `backend/app/schemas.py`：`AgentSessionDetail.usage` 扩展。

### 批次 3：前端设置页模型列表 UI

- `frontend/src/types.ts`：`LlmGroup.models` 改为 `LlmModelInfo[]`（id/context_length/reasoning_efforts）；`LLMModelsResponse` 改为对象数组。
- `frontend/src/api.ts`：`getLlmModels` 返回对象数组。
- `frontend/src/components/LlmConfigForm.tsx`：
  - 模型列表改为列表形式（逐条 id 文本 + context_length InputNumber + reasoning_efforts 多值输入（tags 或列表）+ 删除）。
  - 「获取模型」成功后自动追加所有模型（已存在 id 跳过或更新元数据）。
  - 支持手动新增模型条目；默认模型从列表选择。

### 批次 4：前端 agent 页上下文百分比

- `frontend/src/types.ts` / `api.ts`：`AgentSessionUsage` 增加 `last_input_tokens`/`last_output_tokens`。
- `frontend/src/components/AgentPage.tsx`：
  - 读取当前组所选模型的 `context_length`。
  - 展示「上下文 X / Y tokens（Z%）」（X=last_input_tokens，Y=context_length）；未设 context_length 时仅展示 token 数。
  - 思考强度下拉选项取自所选模型 `reasoning_efforts`（含「默认/不设置」空项），切换模型时更新。

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
- `tests/test_llm_config.py`：模型对象数组、迁移、默认模型 reasoning_efforts 首项。
- `tests/test_api.py`：`/api/llm/models` 元数据解析、config 组接口。
- `tests/test_database.py`：last token 列。
- `tests/test_agent.py` / `test_agent_sessions.py`：usage 细化。

## 验证方式

- 后端：`pytest tests -q`。
- 前端：`npm run build`。
- 手工冒烟：按 acceptance.md 逐项验证。
