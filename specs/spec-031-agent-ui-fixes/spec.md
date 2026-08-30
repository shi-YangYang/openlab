# Spec：Agent 页面 UI 细节修复批（spec-031）

## 元信息

- **Spec 编号**：`spec-031-agent-ui-fixes`
- **状态**：`completed`
- **创建日期**：2026-08-30
- **来源**：spec-030 交付后用户实测反馈
- **负责人**：协调开发 Agent

## 背景与动机

用户实测 Agent 页面发现三个 UI 细节问题：

1. 底部工具栏（加号 / 模型选择 / 思考强度 / 上下文圆环）贴左边缘。
2. 消息区内容贴左边缘。
3. spec-030 的消息悬浮 toolbar：鼠标从消息移向 toolbar 途中 toolbar 即消失，无法到达。

## 需求描述

- FR-1：底部输入区工具栏增加左侧留白，与整体布局协调（`.inputArea` 的 `padding` 左值 0 → 16px）。
- FR-2：消息滚动区内容增加左侧留白（`.messagesScroll` 的 `padding` 左值 0 → 16px）。
- FR-3：消息悬浮 toolbar 的 hover 触发区必须连续：鼠标从消息气泡移动到 toolbar 上不会消失，且悬浮在 toolbar 上时 toolbar 保持可见。实现建议：消除 `.turnToolbar` 的 `top:100% + margin-top:2px` 造成的悬空区（用 `padding-top` 提供视觉间距替代 `margin-top`，toolbar 无背景故不可见，hover 区连续）。
- FR-4（2026-08-30 用户追加）：toolbar 宽度铺满整行（`.turnWrap` 全宽），不再按内容收缩停靠单侧；内部三项保持按消息侧对齐（用户消息靠右、AI 消息靠左），模型名→时间→复制顺序与间距不变。

### 不包含（Out of Scope）

- 其他页面与 Agent 其他区域。
- toolbar 交互形态变更（保持 spec-030 设计）。

## 验收标准

- AC-1：底栏与消息区左侧均有约 16px 留白，视觉不贴边。
- AC-2：鼠标从消息气泡平滑移动到 toolbar，toolbar 保持显示；在 toolbar 上悬停/点击复制均正常。
- AC-3：`npm run build` 通过；pytest 不涉及前端，前端无回归（spec-030 行为不变）。
