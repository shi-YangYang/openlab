# Spec 021 总结

## 元信息

- **Spec 编号**：`spec-021-usability-fixes`
- **状态**：completed（已完成）
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-usability-fixes.md`

## 目标

1. Semantic Scholar 限流可自愈、可选提额、失败原因可见。
2. Agent 输入框增高、模型列表思考强度输入加宽、搜索表单文案友好化。

## 根因说明（Semantic Scholar）

实测官方 Graph API 返回 429 Too Many Requests：未认证共享配额被全局耗尽，属外部限流而非代码回退（spec-013 当年只做接入未处理限流）。本次补齐三层应对。

## 需求清单与实现

- FR-1 重试：429/5xx/网络异常最多重试 2 次；Retry-After 数值秒封顶 5s，解析失败回退退避 1s→2s。
- FR-2 提额：`SEMANTIC_SCHOLAR_API_KEY` 环境变量 → 请求带 `x-api-key` 头。
- FR-3/4 原因透传：fallback 新增 message 字段，前端降级提示展示「官方接口限流(429)，已自动重试仍未恢复」等具体原因。
- FR-5：Agent 输入框 autoSize {minRows:4, maxRows:10}。
- FR-6：模型行 flex 布局，思考强度输入弹性伸展（minWidth 300），不再换行撑高页面。
- FR-7：模式按钮改「直接搜索 / AI 智能搜索」+ Tooltip 解释差异；label 与占位提示直白化。

## 验收结果

- 实施：后端 **274 passed**；前端 build 通过。
- 验收：全部 PASS；改动范围 11 文件无夹带、无密钥硬编码；3 个实施偏差经复核均合理。

## 决策引用

- `.ai/decisions/2026-08-27-usability-fixes.md`

## 使用方式

- 无需配置即可享受自动重试与原因透传；重度使用可在 `backend/.env` 配 `SEMANTIC_SCHOLAR_API_KEY` 提额（申请入口见 .env.example 注释）。

## 遗留观察项（不阻塞）

- A：Radio.Button 包 Tooltip 在 dev 下可能有 ref 运行时告警（build 无错误）；如出现可将子元素用 span 包裹。
- B：spec 未明确 HTTP-date 格式 Retry-After 的处理（现按退避处理）。
- C：其余平台（如百度/知网）的错误处理未纳入本期。
