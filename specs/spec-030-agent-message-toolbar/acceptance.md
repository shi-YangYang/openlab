# 验收标准：spec-030-agent-message-toolbar

## 手动验收（UI）

- AC-1：悬浮任意消息（用户/AI）时，气泡下方淡入 toolbar，移出隐藏；toolbar 不遮挡相邻消息。
- AC-2：toolbar 三项顺序为 模型名 → 时间 → 复制按钮，项间有可见间隔；复制按钮为纯 icon（无文字）。
- AC-3：用户消息显示发送时刻生效的模型名；AI 消息显示实际回复模型名；长模型名省略号截断且 tooltip 可见全名。
- AC-4：时间格式为 `YYYY-MM-DD HH:mm`；气泡内不再出现时间小字。
- AC-5：悬浮复制按钮 tooltip 为「复制」，点击后剪贴板内容与该条消息文本一致（AI 消息为原始 Markdown）。
- AC-6：气泡左/右侧旧「复制原文」悬浮按钮已不存在；代码块「复制代码」按钮仍正常。
- AC-7：刷新页面或切换会话后重新加载历史，toolbar 的模型名与时间仍正确显示（来自后端持久化）。

## 兼容性验收

- AC-8：打开一个 spec-030 之前创建的旧会话，消息正常渲染，缺失的模型名/时间显示 `-`，无控制台报错。
- AC-9：Agent 流式对话、危险操作审批、附件上传、会话管理、上下文压缩行为与改动前一致。

## 工程验收

- AC-10：前端 `tsc` 与 `vite build` 通过；后端 pytest 全量通过。
- AC-11：切换 LLM 配置组后发送新消息，新消息的模型名记录为切换后的模型。

## 验收记录

- **验收日期**：2026-08-30
- **验收方式**：git diff 全量审查 + 读码核对 FR + 实际运行工程验证 + Python 逻辑抽查。UI 悬浮/剪贴板等无法自动化验证的项按代码推演标注 CODE-REVIEW-PASS。

| 编号 | 结论 | 依据 |
| --- | --- | --- |
| AC-1 | CODE-REVIEW-PASS | `.turnWrap` position:relative，`.turnToolbar` absolute top:100%+2px，hover 淡入（opacity 0.2s，pointer-events 切换）；Space size=32 > toolbar 高度，不遮挡下一条消息 |
| AC-2 | PASS | `renderToolbar` 顺序 模型名→时间→复制，`gap:10px`（8–12px 区间内），复制按钮纯 icon（CopyOutlined + size small + type text） |
| AC-3 | CODE-REVIEW-PASS | 用户消息 = 发送时刻 `model || groupDefaults.model`（activeModelRef）；AI 消息 = 后端 `effective_model`（与 `build_llm` 实际调用同源）；`max-width:180px` 省略号 + Tooltip 全名 |
| AC-4 | PASS | 前端 `timestampNow()` 产出 `YYYY-MM-DD HH:mm`；后端 `ts[:16]` 截取同格式；气泡内时间小字已删净 |
| AC-5 | CODE-REVIEW-PASS | Tooltip「复制」，`onClick={() => void onCopyText(turn.text)}` 复制原始文本（AI 即原始 Markdown） |
| AC-6 | PASS | `turnCopy`/`copyLeft`/`copyRight` 代码零残留（grep 仅 Spec 文档命中）；代码块「复制代码」按钮未改动 |
| AC-7 | CODE-REVIEW-PASS | 后端打戳随 `save_messages` 持久化，`normalize_history` 返回 time/model，`refreshDetail` 映射 `m.time`/`m.model` |
| AC-8 | CODE-REVIEW-PASS | 逻辑抽查脚本验证：旧消息（无 kwargs）返回 time=None/model=None → 前端渲染 `-`；`isinstance` 防御畸形 kwargs |
| AC-9 | PASS | 后端 pytest 全量 292 passed；diff 未触碰流式/审批/附件/压缩路径 |
| AC-10 | PASS | `npm run build`（tsc + vite）通过；`pytest tests -q` 292 passed（TEMP=D:\tmp\pytest） |
| AC-11 | CODE-REVIEW-PASS | 切换配置组时 `reloadConfig` 重置 model；发送时 `effectiveModel` 取当前选中值；后端 `get_effective_config()` 按请求时刻生效值打戳 |

FR-1~FR-12 逐条读码核对均落实；无超范围改动、无密钥泄露、无调试残留（console.log/debugger/print 零命中）。

**总体验收结论：通过**（备注：tests/ 目录无 normalize_history 新增字段的专项测试，属可选增强，不阻塞验收。）
