# Spec：上下文占用与模型元数据（spec-019）

## 元信息

- **Spec 编号**：`spec-019-context-usage`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-context-usage.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-018 引入了「模型配置组」与 token 统计，但仍有缺口：

1. agent 页缺少「上下文占用百分比」，无法感知上下文是否将满。
2. 设置页模型列表是标签输入框形式，获取模型后需手动逐个添加，且无法承载每模型元数据。
3. 缺少「上下文长度」配置，无法计算占用百分比；也无法区分同组内不同模型的上下文窗口与默认思考强度。

## 目标

- agent 页展示上下文占用百分比（基于所选模型上下文长度）。
- 设置页模型列表改为列表形式，获取模型时自动追加所有模型。
- 每模型可记录上下文长度、默认思考强度；`/models` 接口尽力返回元数据。

## 范围

### 包含（In Scope）

- 模型列表由字符串数组改为对象数组（id/context_length/reasoning_efforts）。
- `/api/llm/models` 尽力解析并返回每模型上下文长度等元数据。
- 设置页模型列表 UI 改为列表形式 + 自动追加。
- agent 页上下文占用百分比展示。
- 会话 token 统计增加「最近一次调用」维度。

### 不包含（Out of Scope）

- 上下文长度自动探测的精确保证（仅尽力解析常见字段）。
- 组级 reasoning_effort（移除，下沉到每模型）。
- 多用户/权限、配置加密。

## 需求描述

### 功能需求

- FR-1：模型列表结构升级：`llm_config.json` 中组的 `models` 由 `string[]` 改为 `[{id, context_length?, reasoning_efforts?}]`；`reasoning_efforts` 为该模型支持的思考强度选项列表（有序，空表示无/未知）。`default_model` 仍为字符串（引用某模型 id）。组级 `reasoning_effort` 移除。
- FR-2：迁移：加载时把旧结构幂等迁移为新结构——字符串条目转为对象（`context_length` 空、`reasoning_efforts` 继承原组级 reasoning_effort 为单元素列表）；旧的单值 `reasoning_effort` 转为单元素列表；不丢字段。
- FR-3：`get_effective_config()` 返回 `{base_url, api_key, model=default_model, reasoning_effort=默认模型的 reasoning_efforts 首项（空则 ""）}`；现有分析/创新/实验/上传/主题分解调用点无感知。
- FR-4：`POST /api/llm/models` 返回 `models: [{id, context_length?, reasoning_efforts?}]`：尽力从平台响应解析上下文长度（常见字段 `max_context_length`/`context_length`/`context_window`/`max_tokens` 等）与思考强度选项（常见字段 `reasoning_efforts`/`reasoning_effort`/`supported_reasoning_efforts` 等，或依据模型名/能力字段推断的 low/medium/high 集合），解析不到则置 `null`/`[]`；解析失败不影响模型 id 列表返回。
- FR-5：设置页模型列表 UI：
  - 用列表形式（逐条：模型 id 文本 + 上下文长度 InputNumber + 思考强度选项（可输入多个，如 low/medium/high）+ 删除按钮）。
  - 「获取模型」成功后，自动把返回的所有模型追加进该组列表（已存在的 id 跳过或覆盖元数据）。
  - 模型 id 也可手动新增。
- FR-6：agent 页上下文占用百分比：
  - 会话 usage 增加最近一次调用的 `input_tokens`/`output_tokens`。
  - 前端用所选模型的 `context_length` 作分母，最近一次 `input_tokens` 作分子，展示百分比（如「上下文 12,345 / 128,000 tokens（9.6%）」）。
  - 所选模型未配置 `context_length` 时，仅展示 token 数、不显示百分比。
- FR-7：agent 页「思考强度」下拉选项取自所选模型的 `reasoning_efforts`（含「默认/不设置」空项），切换模型时选项与默认值随之更新。

### 非功能需求

- NFR-1：迁移幂等、不丢字段；`context_length`/`reasoning_efforts` 缺失按空处理。
- NFR-2：`/api/llm/models` 解析失败不影响模型 id 列表返回（元数据为空即可）。
- NFR-3：token 统计与百分比计算容错（usage_metadata 缺失按 0）。
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
      "models": [
        { "id": "gpt-4o-mini", "context_length": 128000, "reasoning_efforts": [] },
        { "id": "gpt-4o", "context_length": 128000, "reasoning_efforts": ["low", "medium", "high"] }
      ],
      "default_model": "gpt-4o-mini"
    }
  ]
}
```

## 后端接口草案

- `POST /api/llm/models`：返回 `{ models: [{id, context_length?, reasoning_efforts?}] }`。
- `GET/PUT /api/llm/config`：模型条目为对象数组。
- `GET /api/agent/sessions/{id}`：usage 增加 `last_input_tokens`/`last_output_tokens`。

## 依赖与前置条件

- 依赖 spec-018（配置组 + token 统计）。
- langchain-openai 的 `usage_metadata` 已具备。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 设置页模型列表为列表形式，获取模型自动追加，可编辑上下文长度/思考强度。
- agent 页展示上下文占用百分比。
- 旧配置迁移幂等。
- 后端测试与前端 build 通过。

## 风险与开放问题

- 各平台 `/models` 元数据字段不统一，尽力解析可能不完整，需用户手动补。
- 「最近一次调用 input_tokens」作为上下文大小是近似（不含工具结果之外的瞬时差异），足以反映占用。
- 1M 级 context_length 数值较大，展示时用千分位或「M」单位需注意可读性。
