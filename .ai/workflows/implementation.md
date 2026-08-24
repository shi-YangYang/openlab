# 实施工作流

描述实施 Agent 的任务分配与执行规范。

## 前置条件

- Spec 已确认（`confirmed`）。
- 关键决策已记录到 `.ai/decisions/`。

## 任务分配

协调开发 Agent 创建实施 Agent 时，需提供：

- 完整 Spec（`spec.md`、`plan.md`、`acceptance.md`）。
- 相关决策记录与任务交接文档。
- 必读文件清单（含阅读顺序与冲突优先级）。
- 明确的完成标准（对应验收标准）。

## 实施规范

- 实施 Agent 只负责编码，不负责验收。
- 涉及前后端同时修改时，只派一个实施 Agent。
- 实施过程中遇到需决策的问题，返回协调开发 Agent，不得自行决策。

## 完成后

- 实施 Agent 返回结果报告（见 `.ai/prompts/result-report.md`）。
- 协调开发 Agent 读取报告后，创建验收 Agent 进行独立验收。
- 实施 Agent 完成后立即删除。
