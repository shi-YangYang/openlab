# spec-018 LLM 配置组与 Agent 增强决策

## 决策标题

确定「模型配置组」数据模型、agent 页模型/思考强度选择、以及上下文 token 统计方式。

## 元信息

- **日期**：2026-08-26
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-018-llm-groups

## 背景与问题

1. 当前 LLM 配置是单一扁平结构（base_url/api_key/model/reasoning_effort），无法区分不同平台（oai/ali 等），切换需手动改全部字段。
2. agent 页无模型/思考强度选择，也无法感知当前会话上下文占用。
3. 需要把「模型」从单个改为模型列表，并引入「模型配置组」概念。

## 决策

1. **数据模型**：`data/llm_config.json` 由扁平结构改为 `{ active_group, groups: [...] }`，每组字段：`id`（唯一）、`name`、`base_url`、`api_key`、`models`（列表）、`default_model`、`reasoning_effort`（默认值）。`active_group` 标记当前使用组；旧扁平配置首次加载时迁移为单个「默认」组。
2. **有效配置**：`get_effective_config()` 返回当前组的 `{base_url, api_key, model=default_model, reasoning_effort}`，现有分析/创新/实验/上传/主题分解等调用点无需改动。
3. **思考强度**：每个配置组各带一个默认 `reasoning_effort`，agent 页可临时覆盖。
4. **agent 页选择范围**：仅在当前组的模型列表里选模型 + 选思考强度（切换配置组仍在设置页）。
5. **上下文统计**：真实 token——从每次 LLM 调用的 `AIMessage.usage_metadata` 累加输入/输出 token，持久化到会话，展示「输入 X / 输出 Y tokens」。
6. **agent 模型/强度传递**：`AgentChatRequest`/`AgentApproveRequest` 增加可选 `model`、`reasoning_effort`，未传时回落当前组默认；`build_llm` 接受覆盖参数。

## 理由

- 配置组天然对应不同平台，切换即用；模型列表让单组内也能选不同模型。
- 复用 `get_effective_config` 的语义使现有调用点零改动，改动面最小。
- 真实 token 比估算准确，且 API 已返回 usage 元数据，成本低。

## 影响与后果

- 后端：`llm_config.py` 重构为组结构 + 迁移；`schemas.py` 新增组模型；`main.py` 改 `/api/llm/config` 与 agent 请求；agent 循环捕获 usage 并持久化（`agent_sessions` 表加 token 列）。
- 前端：设置页 LlmConfigForm 重构为组管理；agent 页加模型/强度选择与上下文展示；`api.ts`/`types.ts` 更新。
- 数据迁移：旧 `llm_config.json` 自动迁移为单组，不丢配置。
