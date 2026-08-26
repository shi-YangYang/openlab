# Spec 018 总结

## 元信息

- **Spec 编号**：`spec-018-llm-groups`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-llm-groups.md`

## 目标

1. LLM 配置由单一扁平结构改为「模型配置组」，区分不同平台（oai/ali 等），可切换当前使用组。
2. agent 页支持选择模型与思考强度。
3. agent 页展示当前会话上下文 token 使用情况。

## 技术栈

- 后端：`llm_config.py` 组化 + 旧配置自动迁移；`agent_sessions` 表新增 token 列；`AIMessage.usage_metadata` 统计真实 token。
- 前端：设置页组管理表单、agent 页模型/强度下拉与上下文展示。

## 需求清单

- FR-1：`llm_config.json` 改为 `{active_group, groups}`，旧扁平配置迁移为单组。
- FR-2：`get_effective_config()` 返回当前组默认，现有调用点零改动。
- FR-3：`GET/PUT /api/llm/config` 组结构，复用 models/test/presets。
- FR-4：agent chat/approve 支持 model/reasoning_effort 覆盖。
- FR-5：会话 token 统计并持久化。
- FR-6：设置页配置组管理。
- FR-7：agent 页模型/强度选择 + 上下文展示。

## 接口

- `GET/PUT /api/llm/config`（组结构）
- `POST /api/llm/models`、`POST /api/llm/test`、`GET /api/llm/presets`（复用）
- `POST /api/agent/chat`、`POST /api/agent/approve`（新增 model/reasoning_effort）
- `GET /api/agent/sessions/{id}`（新增 usage）

## 验收结果

- 实施 Agent：后端 `pytest tests -q` → **251 passed**；前端 `npm run build` 通过。
- 验收 Agent：AC-1~AC-4 + 回归全部 **PASS**；迁移幂等、无密钥硬编码、改动范围仅限 spec-018 相关文件。无返工项。

## 决策引用

- `.ai/decisions/2026-08-26-llm-groups.md`

## 使用方式

- 设置页管理多个配置组（新增/编辑/删除/切换当前组/获取模型/测试连接）。
- agent 页顶部选择模型与思考强度，发送后生效；上下文 token 用量实时展示。

## 遗留问题

- 上下文窗口上限未做（不同模型各异，本次仅展示 token 用量，不做「X/Y」上限）。
- 配置组 api_key 仍明文存本地文件（沿用现状，个人自用）。
