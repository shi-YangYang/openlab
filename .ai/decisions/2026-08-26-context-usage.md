# spec-019 上下文占用与模型元数据决策

## 决策标题

确定上下文占用百分比、模型列表形态、以及每模型元数据（上下文长度/思考强度）的来源与粒度。

## 元信息

- **日期**：2026-08-26
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-019-context-usage

## 背景与问题

1. spec-018 已引入「模型配置组」与 token 统计，但缺少「上下文占用百分比」。
2. 设置页模型列表当前是标签输入框形式，且获取模型后需手动逐个添加。
3. 需要为每个模型记录「上下文长度」「思考强度」等元数据，用于计算占用百分比与作为默认值。

## 决策

1. **每模型元数据**：模型列表由 `string[]` 改为对象数组 `[{ id, context_length?, reasoning_effort? }]`；`context_length` 为该模型上下文窗口（token 数，如 1M = 1048576），`reasoning_effort` 为该模型默认思考强度（可空）。组级 `reasoning_effort` 移除，改为随默认模型。
2. **元数据来源**：「API 尽力读 + 手动补」——`POST /api/llm/models` 尽力解析平台返回的上下文长度等字段（常见 `max_context_length`/`context_length`/`context_window` 等），读不到则置空；用户在列表里手动补。
3. **上下文长度粒度**：每个模型一个（百分比按所选模型算）。
4. **模型列表 UI**：改为列表形式（逐条展示 id/上下文长度/思考强度，可删除），「获取模型」自动把平台返回的所有模型追加进列表。
5. **上下文占用百分比**：分母 = 所选模型的 `context_length`；分子 = 当前上下文 token（最近一次 LLM 调用的 `input_tokens`，即完整上下文大小）。未设置 context_length 时仅展示 token 数、不显示百分比。
6. **token 统计细化**：会话在累计输入/输出 token 之外，额外记录最近一次调用的 `input_tokens`/`output_tokens`，用于百分比。

## 理由

- 每模型粒度最贴合实际（同组内不同模型上下文窗口可不同）。
- API 不保证返回元数据，故「尽力读 + 手动补」兼顾自动化与可控。
- 百分比用「最近一次调用的 input_tokens」而非累计值，才能真实反映当前上下文占用（每次调用都会重发完整历史）。

## 影响与后果

- 后端：`llm_config.py` 模型条目结构迁移（string→对象，组级 reasoning_effort 下沉）；`/api/llm/models` 返回带元数据的对象列表；agent 会话 token 统计增加「最近一次」维度；`get_effective_config` 的 reasoning_effort 取自默认模型。
- 前端：设置页模型列表改列表 UI + 自动追加；agent 页增加上下文占用百分比。
- 迁移：已存在的 spec-018 组结构（models 为字符串数组）需二次迁移为对象数组。
