# Spec 027 总结

## 元信息

- **Spec 编号**：`spec-027-refactor`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-refactor.md`

## 目标

1. 前端样式系统重构：CSS Modules + 公共 CSS 类，行内样式 212 → ≤ 60
2. 前端大文件拆分为组件化子组件
3. 后端 main.py / database.py 拆为模块化结构

## 重构成果

### 后端
| 原文件 | 行数 | 拆为 | 结果 |
|---|---|---|---|
| database.py | 1058 | db/ 包（8 文件，按表拆分，__init__ re-export 兼容） | ✅ |
| main.py | 1631 | app.py(66) + routes/（12 文件：papers/agent/servers/experiments/llm/platforms/search/innovations/analyses/reviews/translation） | ✅ |

- 后端模块化标准：imports 三段分组、router 声明、端点按 HTTP 方法分组、HTTPException 统一、延迟导入仅避免循环依赖
- 路由顺序保持（translation/pdf 在 /pdf 前）

### 前端
| 原文件 | 行数 | 拆为 | 结果 |
|---|---|---|---|
| AgentPage.tsx | 1176 | agent/ 目录（入口 95 行 + 5 子组件 + module.css 319 行） | ✅ |
| ServerDetailPage.tsx | 551 | server/ 目录（入口 49 行 + 3 Section + module.css 67 行） | ✅ |
| ExperimentRunPanel.tsx | 539 | experiment-run/ 目录（入口 298 行 + CreateView 125 + RunView 176 + constants.ts + module.css 124 行） | ✅ |
| LlmConfigForm.tsx | 522 | llm-config/ 目录（入口 298 行 + GroupList 78 + GroupForm 178 + module.css 87 行） | ✅ |
| TitleBar.tsx | 12 处行内样式 | TitleBar.module.css（0 行内样式） | ✅ |

- 行内样式 212 → **54**（减少 75%）
- 6 个公共 CSS 类提取到 index.css（.text-secondary-12/.page-center/.code-block/.log-area/.file-chip/.section-title），25 处引用

### 组件化标准

- 前端：imports 三段分组 → 常量 → Props 接口 → 工具函数 → 子组件 → 主组件（hooks→派生→handle*→JSX）
- 后端：imports 三段分组 → router → 共享 helper → 端点按 HTTP 方法分组 → helper 置底
- NFR-6 逐文件抽查：AgentChatInput / LlmConfigGroupForm 均合规

## 验收结果

- 后端 **292 passed**；前端 build + electron tsc 通过
- 验收：首次 2 项 FAIL（行内样式 99 > 60、AgentPage 651 > 100），返工后复验 **5/5 PASS**
- 附加修复：papers.py 中 `redact` 未导入的潜在 NameError（→ translation.py 内实现）

## 决策引用

- `.ai/decisions/2026-08-28-refactor.md`

## 遗留问题

- server/ 三个 Section 子组件直接调用 API（spec 说子组件不直接调 API，但为最小迁移保留）
- routes/experiments.py 的 runs_router 5 端点未声明 response_model（历史遗留）
