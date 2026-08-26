# Spec 019 验收清单

## 准备

1. 后端启动、前端启动。
2. 已有 spec-018 的组结构配置，或一份旧扁平配置。
3. 一个 OpenAI 兼容平台凭据（用于获取模型/测试连接/真实对话）。

## AC-1 模型列表结构（FR-1 / FR-2）

- [ ] `GET /api/llm/config` 返回的组 `models` 为对象数组，含 `id`/`context_length`/`reasoning_efforts`。
- [ ] 旧结构（字符串数组或组级 reasoning_effort / 单值 reasoning_effort）加载后幂等迁移为对象数组（reasoning_efforts 为列表），字段不丢。
- [ ] `get_effective_config()` 的 model 与 reasoning_effort 取自默认模型（reasoning_efforts 首项）。

## AC-2 获取模型元数据（FR-4）

- [ ] `POST /api/llm/models` 返回对象数组；平台返回了上下文长度/思考强度选项字段时被解析填入，否则为空。
- [ ] 解析失败不影响模型 id 列表返回。

## AC-3 设置页模型列表 UI（FR-5）

- [ ] 模型列表为列表形式（逐条展示），不是标签输入框。
- [ ] 每条可编辑：模型 id、上下文长度、思考强度选项（可输入多个）；可删除某条。
- [ ] 点击「获取模型」后自动把平台返回的所有模型追加进列表（已存在 id 不重复）。
- [ ] 默认模型可从列表中选择。

## AC-4 上下文占用百分比（FR-6 / FR-7）

- [ ] agent 页展示「上下文 X / Y tokens（Z%）」，X 为最近一次调用 input_tokens，Y 为所选模型 context_length。
- [ ] 所选模型未设 context_length 时，仅展示 token 数、无百分比。
- [ ] 切换模型后分母随所选模型的 context_length 更新。
- [ ] 思考强度下拉选项取自所选模型 reasoning_efforts（含「默认/不设置」空项），切换模型时更新。

## 回归

- [ ] 搜索、分析、创新点、实验方案、上传、Agent、服务器管理均正常。
- [ ] 后端 `pytest tests -q` 全部通过。
- [ ] 前端 `npm run build` 通过。
