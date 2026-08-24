# spec-001 汇总：文献搜索与下载（arXiv）

> 本文档汇总 spec-001 从需求、实施到验收的全部结论，替代分散在 `spec.md`、`plan.md`、`acceptance.md` 及各轮验收记录中的临时信息。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-001-paper-search-download`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：
  - `.ai/decisions/2026-08-24-project-kickoff.md`（产品形态、数据源、LLM、用户规模、优先级）
  - `.ai/decisions/2026-08-24-backend-stack.md`（Python + FastAPI、SQLite）
  - `.ai/decisions/2026-08-24-frontend-stack.md`（React + TS + Vite + Ant Design）
  - `.ai/decisions/2026-08-24-llm-orchestration.md`（LangChain + 多平台预设）

## 背景与目标

openlab 科研流程的第一步：自动从 arXiv 搜索并下载相关论文，为后续论文分析、创新点设计提供输入。

- 通过 Web 界面发起 arXiv 搜索（关键词/检索式，或主题描述由 LLM 拆解）。
- 自动下载命中论文的 PDF 全文与元数据；PDF 存本地目录、元数据入库 SQLite。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python + FastAPI |
| 前端 | React + TypeScript + Vite + Ant Design |
| LLM | LangChain（`langchain` + `langchain-openai`），`ChatOpenAI` 自定义 base_url，OpenAI 兼容 |
| 存储 | 元数据 SQLite；PDF 本地 `data/papers/`；LLM 配置本地 `data/llm_config.json` |
| 启动 | `start.ps1` + concurrently 合并输出 |

## 功能需求清单（全部完成）

- FR-1：关键词/检索式搜索 arXiv。
- FR-2：主题描述 → LLM 拆解为检索式 → 搜索。
- FR-3：结果列表展示标题、作者、摘要、分类、日期、arXiv ID。
- FR-4：可配置返回数量（1~100），支持分类/日期过滤。
- FR-5：下载选中/全部论文 PDF 到本地目录。
- FR-6：元数据入库 SQLite，按 arXiv ID 去重跳过。
- FR-7：展示下载进度/状态。
- FR-8：LLM 调用基于 LangChain ChatOpenAI（自定义 base_url）。
- FR-9：平台预设列表 + 前端下拉选择 + 自定义。
- FR-10：LLM 配置持久化到本地文件（非数据库、不入 git），密钥不硬编码/不入库。
- FR-11：一键启动脚本 `start.ps1`（检测/安装依赖 + concurrently 合并输出，端口可配置，默认 8001）。

非功能：NFR-1 密钥经配置提供；NFR-2 遵守 arXiv 限速（间隔 + 指数退避）；NFR-3 单用户无鉴权。

## 后端接口

- `GET /api/health` — 健康检查
- `POST /api/search` — 关键词搜索
- `POST /api/search/topic` — 主题描述搜索（LLM 拆解）
- `POST /api/download` — 下载 PDF（后台任务）
- `GET /api/papers` — 查询已下载论文
- `GET /api/llm/presets` — LLM 平台预设列表
- `GET /api/llm/config` / `PUT /api/llm/config` — LLM 配置读写

## 验收结果

验收标准 AC-1 ~ AC-12 **全部 PASS**。

| 轮次 | 结果 | 说明 |
|---|---|---|
| 1 | PASS | 核心功能（搜索/下载/去重/状态），14 个 pytest 通过 |
| 2 | PASS | 补充 LangChain + 多平台预设 + 配置持久化（AC-9~11），25 个 pytest 通过 |
| 3 | BLOCKED | 启动脚本静态验证通过，但 Docker 占用端口 8000 阻塞端到端运行 |
| 4 | PASS | 端口返工：默认 8001 + 可配置，端到端实测通过 |

- 自动化测试：后端 `pytest` **25 passed**；前端 `npm run build` 通过。
- 端到端：`start.ps1`（默认 8001 / `-Port` / `OPENLAB_PORT`）启动，后端 `/api/health` 与前端页面均可访问。

## 使用方式

```powershell
cd E:\gitTools\openlab
.\start.ps1                 # 一键启动，默认后端 8001、前端 5174
.\start.ps1 -Port 9000      # 指定后端端口
$env:OPENLAB_PORT=9000; .\start.ps1   # 环境变量指定（-Port 优先）
```

- 浏览器打开 http://localhost:5174。
- 关键词搜索无需 LLM；主题搜索需先在「LLM 配置」选平台并填 API Key（或 `PUT /api/llm/config`）。
- LLM 平台预设：OpenAI、DeepSeek、阿里云百炼、硅基流动、智谱 GLM、Moonshot Kimi（`backend/app/presets.py` 单行可扩展）。

## 遗留问题（非阻塞）

1. 真实 LLM 主题拆解需配置有效 `api_key` 与正确的模型 ID（模型名必须用平台真实支持的 ID）。
2. 前端构建产物 chunk 偏大（~1.13 MB）——性能告警，不影响功能。
3. `GET /api/llm/config` 明文返回 api_key——单用户本地场景回填表单用，无鉴权下可接受。
