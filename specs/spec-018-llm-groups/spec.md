# Spec：LLM 配置组与 Agent 增强（spec-018）

## 元信息

- **Spec 编号**：`spec-018-llm-groups`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-llm-groups.md`
- **负责人**：协调开发 Agent

## 背景与动机

1. 当前 LLM 配置为单一扁平结构（base_url/api_key/model/reasoning_effort），无法区分不同平台（oai/ali 等），切换平台需手动改全部字段。
2. agent 页无模型/思考强度选择，无法按会话切换模型；也看不到当前会话上下文占用。
3. 需把「模型」从单个改为模型列表，并引入「模型配置组」概念区分不同平台。

## 目标

- 设置页支持「模型配置组」管理：每组含 base_url/api_key/模型列表/默认模型/默认思考强度，可切换当前使用组。
- agent 页支持选择模型与思考强度，并展示当前会话上下文 token 使用情况。
- 旧配置自动迁移，不丢数据。

## 范围

### 包含（In Scope）

- 后端 LLM 配置改为配置组结构 + 旧配置迁移。
- 设置页配置组管理 UI。
- agent 页模型选择、思考强度选择、上下文 token 展示。
- agent 会话 token 用量统计与持久化。
- agent 请求携带模型/思考强度覆盖。

### 不包含（Out of Scope）

- 配置组加密存储（仍明文存本地文件，沿用现状）。
- 上下文窗口上限自动探测（不同模型上下文窗口各异，本次仅展示 token 用量，不做「X/Y」上限）。
- 多用户/权限。
- agent 页配置组切换（切换组在设置页，见决策）。

## 需求描述

### 功能需求

- FR-1：后端 `data/llm_config.json` 结构改为 `{ active_group, groups: [...] }`：
  - 组字段：`id`（唯一字符串）、`name`、`base_url`、`api_key`、`models`（字符串列表）、`default_model`、`reasoning_effort`（可选）。
  - 首次加载检测到旧扁平结构时，自动迁移为单个组（id=`default`、name=`默认`），并设置 `active_group=default`，不丢字段。
  - 无配置文件/无组时，回落环境变量（LLM_BASE_URL/LLM_API_KEY/LLM_MODEL/LLM_REASONING_EFFORT）或内置默认，合成一个默认组。
- FR-2：`llm_config.get_effective_config()` 返回当前组 `{base_url, api_key, model=default_model, reasoning_effort}`；现有分析/创新点/实验/上传/主题分解等调用点无感知、无需改动。
- FR-3：新增 LLM 配置组 API：
  - `GET /api/llm/config` → `{ active_group, groups: [LLMGroup] }`。
  - `PUT /api/llm/config` → 整体保存 `{ active_group, groups }`。
  - 复用 `POST /api/llm/models`、`POST /api/llm/test`、`GET /api/llm/presets`（入参为单组 base_url/api_key/model，设置页按组调用）。
- FR-4：agent 请求支持模型/强度覆盖：
  - `AgentChatRequest`、`AgentApproveRequest` 增加可选 `model`、`reasoning_effort`。
  - `agent.agent.build_llm(model=None, reasoning_effort=None)` 接受覆盖；未传时使用当前组默认。
  - 运行循环（chat→多步→approve）内保持同一次选择的模型/强度一致（实现可存于 pending 或前端每次携带，实施时取最简一致方案）。
- FR-5：agent 上下文 token 统计：
  - 每次 LLM 调用后从 `AIMessage.usage_metadata` 读取 `input_tokens`/`output_tokens`，累计到会话。
  - `agent_sessions` 表新增 `input_tokens`、`output_tokens` 两列（默认 0，沿用 `_migrate` 机制）。
  - `get_session_detail` 返回 `usage: { input_tokens, output_tokens, total_tokens, message_count }`。
- FR-6：设置页 `LlmConfigForm` 重构为配置组管理：
  - 展示配置组列表（每组的 name、base_url、模型列表、默认模型、思考强度）。
  - 支持新增/编辑/删除组；标记「当前使用」组或切换 active_group。
  - 每组可「获取模型」（填充该组 models）、「连通性测试」。
  - 保存时 `PUT /api/llm/config` 整体提交。
- FR-7：agent 页增强：
  - 顶部（或输入区附近）增加「模型」下拉（选项来自当前组的 `models`，默认 `default_model`）与「思考强度」下拉（low/medium/high/留空，默认当前组 `reasoning_effort`）。
  - 发送/确认时携带所选 model 与 reasoning_effort。
  - 展示当前会话上下文使用：`输入 X / 输出 Y tokens`（来源 session detail 的 `usage`）。

### 非功能需求

- NFR-1：配置组 API 响应不含敏感信息外的额外暴露（api_key 沿用现状明文返回，个人自用本地文件，不入库不入 git）。
- NFR-2：旧配置迁移幂等，重复加载不重复迁移；迁移前原文件保留语义。
- NFR-3：token 统计容错：`usage_metadata` 缺失时按 0 处理，不影响 agent 主流程。
- NFR-4：改造后 `pytest tests -q` 通过、`npm run build` 通过。

## 数据结构约定

`data/llm_config.json`（新）：

```json
{
  "active_group": "oai",
  "groups": [
    {
      "id": "oai",
      "name": "OpenAI",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "models": ["gpt-4o-mini", "gpt-4o"],
      "default_model": "gpt-4o-mini",
      "reasoning_effort": "medium"
    }
  ]
}
```

`agent_sessions` 表新增：`input_tokens INTEGER DEFAULT 0`、`output_tokens INTEGER DEFAULT 0`。

## 后端接口草案

- `GET /api/llm/config` → `{ active_group, groups }`
- `PUT /api/llm/config` → 保存 `{ active_group, groups }`
- `POST /api/llm/models`（复用）、`POST /api/llm/test`（复用）、`GET /api/llm/presets`（复用）
- `POST /api/agent/chat`：请求体新增 `model?`、`reasoning_effort?`
- `POST /api/agent/approve`：请求体新增 `model?`、`reasoning_effort?`
- `GET /api/agent/sessions/{id}`：返回体新增 `usage`

## 依赖与前置条件

- 依赖 spec-010/011/012（Agent）、spec-015（LLM 配置 reasoning_effort）。
- langchain-openai 已返回 `usage_metadata`（langchain>=0.3 / langchain-openai>=0.2，满足）。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 设置页可管理多组、切换当前组、获取模型、测试连接。
- 旧配置自动迁移不丢数据。
- agent 页可切换模型与思考强度并生效。
- agent 页展示上下文 token 用量，随对话增长。
- 后端测试与前端 build 通过。

## 风险与开放问题

- 旧配置迁移需覆盖多种形态（空文件、扁平结构、已含 reasoning_effort）。
- 不同平台 `/models` 接口返回格式差异，沿用 spec-015 的容错（失败可手动输入模型名）。
- `usage_metadata` 是否由平台返回取决于平台实现，缺失时按 0 展示（不阻塞）。
