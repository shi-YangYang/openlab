# Spec 019 总结

## 元信息

- **Spec 编号**：`spec-019-context-usage`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-context-usage.md`

## 目标

1. agent 页展示上下文占用百分比。
2. 设置页模型列表改为列表形式，获取模型自动追加。
3. 每模型记录上下文长度、思考强度选项；`/models` 尽力返回元数据。

## 技术栈

- 后端：模型条目结构升级（string[] → `{id, context_length?, reasoning_efforts?}`）+ 二次迁移；`/api/llm/models` 尽力解析上下文长度与思考强度选项；`agent_sessions` 新增最近一次 token 维度。
- 前端：设置页模型列表 UI、agent 页百分比与思考强度下拉。

## 需求清单

- FR-1：`models` 升级为 `[{id, context_length?, reasoning_efforts?}]`（`reasoning_efforts` 为选项列表）。
- FR-2：旧结构幂等迁移（字符串条目→对象；旧单值 reasoning_effort→单元素列表；组级下沉）。
- FR-3：`get_effective_config` 的 reasoning_effort 取默认模型 `reasoning_efforts` 首项。
- FR-4：`/api/llm/models` 返回带元数据对象数组（尽力解析上下文长度与思考强度选项）。
- FR-5：设置页模型列表 UI（列表形式、逐条编辑/删除/新增、获取模型自动追加）。
- FR-6：agent 页上下文占用百分比。
- FR-7：agent 页思考强度下拉选项取自所选模型 `reasoning_efforts`。

## 接口

- `POST /api/llm/models` → `{models: [{id, context_length?, reasoning_efforts?}]}`
- `GET/PUT /api/llm/config`（模型条目为对象数组）
- `GET /api/agent/sessions/{id}`（usage 增 last_input_tokens/last_output_tokens）

## 验收结果

- 实施（含返工）：后端 `pytest tests -q` → **258 passed**；前端 `npm run build` 通过。
- 验收（含返工）：全部 **PASS**；迁移幂等、无密钥硬编码、改动范围正确。无返工项。

## 决策引用

- `.ai/decisions/2026-08-26-context-usage.md`

## 使用方式

- 设置页管理各配置组模型列表（逐条编辑上下文长度、思考强度选项；获取模型自动追加）。
- agent 页展示「上下文 X / Y tokens（Z%）」，分母为所选模型上下文长度；思考强度下拉选项来自所选模型。

## 遗留问题

- 各平台 `/models` 元数据字段不统一，上下文长度/思考强度选项可能需用户手动补。
- 组级 `reasoning_effort` 字段在 schema 保留为可选（兼容输入），归一化后不再出现在响应中。
