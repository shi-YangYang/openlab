# Spec 025 总结

## 元信息

- **Spec 编号**：`spec-025-agent-attachments`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-agent-attachments.md`

## 目标

Agent 页支持上传本地文件/文件夹到会话沙箱，Agent 可直接读取作为上下文。

## 需求清单与实现

- FR-1：`POST /api/agent/sessions/{id}/attachments`（multipart），写入沙箱，路径穿越防护 ✅
- FR-2：「+」Popover 菜单（文件/文件夹选择器、隐藏 input、上传中 Spin） ✅
- FR-3：上传完成自动发提示消息进 LLM 上下文（真实 WS 用户气泡） ✅
- FR-4：已上传文件 Tag 列表（相对路径、closable） ✅

## 验收结果

- 后端 **292 passed**（新增 4 个附件用例：正常上传/文件夹层级/穿越清洗/无会话 404）；前端 build 通过。
- 验收：4/4 FR **PASS**；安全核查（落点与 sandbox_dir 一致、穿越断言）通过；改动范围仅 spec-025 文件。

## 决策引用

- `.ai/decisions/2026-08-28-agent-attachments.md`

## 遗留说明

- 无会话上传返回 404（spec 写 400），提示文案由前端承担——属 spec 包内措辞不一致，行为满足 AC-3。
- webkitdirectory 在 Firefox 支持有限（Chrome/Edge 完整）。
