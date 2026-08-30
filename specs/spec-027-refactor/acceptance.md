# Spec 027 验收清单

## AC-1 后端拆分

- [ ] `main.py` 拆为 `app.py` + `routes/` 包（8 个 APIRouter 文件），`uvicorn app.main:app` 启动兼容。
- [ ] `database.py` 拆为 `db/` 包，所有 `from .. import database` 调用不破坏。
- [ ] 路由注册顺序保持（translation/pdf 在 /pdf 之前）。
- [ ] `pytest tests -q` 全部通过。

## AC-2 前端拆分

- [ ] AgentPage 拆为 agent/ 目录 5 个子组件，行为一致。
- [ ] ServerDetailPage 拆为 server/ 目录 4 个子组件。
- [ ] ExperimentRunPanel 拆为 experiment-run/ 目录 2 个子组件。
- [ ] LlmConfigForm 拆为 llm-config/ 目录 2 个子组件。
- [ ] `npm run build` 通过。

## AC-3 样式重构

- [ ] 公共 CSS 类提取到 index.css（≥ 5 个公共类）。
- [ ] AgentPage / ExperimentRunPanel / LlmConfigForm / TitleBar / ServerDetailPage 使用 `.module.css`。
- [ ] 行内样式数量从 212 减少到 ≤ 60（减少 70%+）。

## AC-4 全流程回归

- [ ] `npm run electron:dev` 启动正常。
- [ ] 搜索→下载→分析→创新点→实验方案→执行 全流程正常。
- [ ] Agent 对话/审批/附件/翻译 正常。
- [ ] 服务器管理/部署/终端 正常。
