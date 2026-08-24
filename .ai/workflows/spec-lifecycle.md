# Spec 生命周期工作流

描述一个 Spec 从起草到验收完成的完整流程。

## 流程

1. **起草（draft）**
   - 协调开发 Agent 与用户沟通需求，澄清关键决策。
   - 协调开发 Agent 编写 `spec.md`、`plan.md`、`acceptance.md`。
   - 关键决策记录到 `.ai/decisions/`。

2. **确认（confirmed）**
   - 用户确认 Spec 内容。
   - Spec 状态由 `draft` 更新为 `confirmed`。

3. **实施（implementing）**
   - 协调开发 Agent 创建实施 Agent，传入完整上下文（Spec、决策、必读文件清单）。
   - 实施 Agent 按 `plan.md` 实施，完成后返回结果报告。
   - 状态更新为 `implementing`。

4. **验收（accepted / reworking）**
   - 协调开发 Agent 创建新的验收 Agent，独立验收。
   - 验收通过 → 状态 `accepted`。
   - 验收未通过 → 进入返工流程（见 `rework.md`）。

5. **完成收尾（completed）**
   - Spec 通过最终验收后，协调开发 Agent 执行收尾（见 `completion.md`）：
     - 标记 `spec.md` 状态为 `completed`。
     - 汇总临时/验收 md 文档为一个 `summary.md`。
     - 安全核查后 commit 并 push。

## 状态流转

```
draft → confirmed → implementing → accepted → completed
                         ↑            ↓
                         └── reworking ┘（验收失败后返工）
```

## 约束

- 关键问题未确认前，不得开始实施。
- 实施 Agent 与验收 Agent 相互独立，验收 Agent 不得修改业务代码。
