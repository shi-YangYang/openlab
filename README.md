# openlab

<p align="center">
  <img src="docs/logo.png" alt="openlab logo" width="180" />
</p>

**简体中文** | [English](README.en.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/🦜🔗-LangChain-green.svg)](https://www.langchain.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Ant Design](https://img.shields.io/badge/Ant%20Design-5-0170FE.svg?logo=antdesign&logoColor=white)](https://ant.design/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33.svg?logo=playwright&logoColor=white)](https://playwright.dev/)
[![WebSocket](https://img.shields.io/badge/WebSocket-realtime-orange.svg)](https://developer.mozilla.org/docs/Web/API/WebSocket)

开源科研 Agent 框架：文献挖掘 → 假设生成 → 实验设计 → SSH 部署执行，全流程自动化。

openlab 将科研流程装进一个浏览器工作台：多平台文献搜索与下载、LLM 论文分析与综述、创新点与实验方案生成，以及一个能自主调用工具完成上述全流程的流式对话 Agent，并支持一键部署到远程 GPU 服务器（SSH + Web 终端）。

## 目录

- [安全](#安全)
- [背景](#背景)
- [安装](#安装)
- [使用](#使用)
- [功能总览](#功能总览)
- [架构与技术栈](#架构与技术栈)
- [API](#api)
- [配置](#配置)
- [维护者](#维护者)
- [贡献](#贡献)
- [许可证](#许可证)

## 安全

- LLM API Key 与 SSH 凭据仅保存在本地配置文件（`backend/data/`，已被 gitignore），绝不硬编码、不入库。
- 下载的 PDF、SQLite 数据库、会话数据均在 `backend/data/` 下，不会进入版本控制。
- Agent 的危险操作（远程命令、代码执行等）必须经用户在界面上逐次确认才会执行；工具输出中的凭据会被自动脱敏。
- 禁止提交 `.env` 文件或任何真实密钥。

## 背景

科研人员的大量时间消耗在重复劳动上：搜文献、下 PDF、读论文写综述、想创新点、配环境、跑实验。openlab 把这条链路搬进一个统一的界面：

1. **文献挖掘** — arXiv / Semantic Scholar / 百度学术 / 知网 多平台搜索，PDF 下载进度可视，也可上传自己的 PDF。
2. **论文理解** — LLM 自动分析论文（研究问题/方法/结论/实验维度），多篇对比综述。
3. **假设生成** — 基于选中论文自动提出创新点，并可一键转化为结构化实验方案。
4. **部署执行** — SSH 服务器管理、git clone/SFTP 部署、GPU 监控、交互式 Web 终端。
5. **Agent 贯穿全程** — 用自然语言下达科研目标，Agent 自主编排以上所有能力。

项目遵循规格驱动开发（SDD）与多 Agent 协作工作流，全部演进记录见 [specs/](specs/)，协作约定见 [AGENTS.md](AGENTS.md)。

## 安装

### 前置依赖

- [Python](https://www.python.org/) 3.10+
- [Node.js](https://nodejs.org/) 18+
- Windows PowerShell（一键脚本目前为 `.ps1`）

### 一键启动

```powershell
cd openlab
.\start.ps1
```

脚本会自动检测并安装缺失依赖（Python 虚拟环境、后端 pip 包、Node/npm 包），然后合并输出启动前后端。

### 手动安装

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # 可选：填写环境变量级配置
uvicorn app.main:app --reload --port 8001

# 前端
cd ..\frontend
npm install
npm run dev                  # http://localhost:5174
```

## 使用

```powershell
.\start.ps1                  # 后端 8001，前端 5174
.\start.ps1 -Port 9000       # 自定义后端端口
```

浏览器打开 <http://localhost:5174>，建议按以下顺序上手：

1. **配置 LLM**：设置页 → 「LLM 配置」→ 新建配置组（选平台预设或填 OpenAI 兼容 Base URL + API Key）→「获取模型」拉取模型列表 → 选默认模型与思考强度 → 保存。支持多个配置组随时切换不同平台。
2. **搜索文献**：搜索页选择「直接搜索」（原样提交各平台）或「AI 智能搜索」（LLM 把研究主题改写成检索式）；勾选平台后搜索，结果可多选下载。
3. **分析论文**：论文库中对已下载论文点「分析」，进入二级页面查看结构化分析结果并导出 Markdown；多选可发起对比综述与创新点设计。
4. **使用 Agent**：Agent 页用自然语言下达目标（如“搜索注意力机制相关论文，下载并分析前 2 篇”），回复实时流式输出，危险操作会在弹窗中请求确认，长对话接近模型上下文上限时自动压缩历史。
5. **连接服务器**（可选）：服务器页添加 SSH 凭据 → 测试连接 → git clone 或上传代码 → 查看 GPU 监控或打开 Web 终端。

> 若本机无法直连 arXiv / Semantic Scholar 等站点（搜索失败或下载卡住），请在 设置页 →「网络代理」填入本机代理（如 Clash 的 `127.0.0.1:7897`），保存即生效。

## 功能总览

### 文献搜索与论文库

- 四大平台并发搜索：arXiv、Semantic Scholar（官方 Graph API，限流自动重试）、百度学术、知网（浏览器登录态）。
- 「直接搜索」与「AI 智能搜索」两种模式；返回数量、分类、日期过滤。
- PDF 批量下载带进度条与状态管理；本地存储、去重、删除清理。
- 本地 PDF 上传：自动提取元数据与来源链接，可手动修正。

### LLM 分析

- 单篇论文四维结构化分析、多篇对比综述、创新点设计、实验方案设计，均支持中英双语与 Markdown 导出。
- 模型配置组：按平台（OpenAI / DeepSeek / 阿里云百炼 / 硅基流动 / 智谱 GLM / Moonshot Kimi…）管理多组配置，随时切换当前组。
- 每个模型独立维护上下文长度与思考强度选项（内置常见推理强度词典，获取模型时自动填充，可手动调整）。

### 科研 Agent

- WebSocket 流式对话：token 级实时输出、工具执行状态实时推送、无需轮询。
- 可视化工具调用：每一步工具的参数/结果可折叠查看，失败的调用默认展开。
- 全生命周期控制：运行中可一键停止中断；断线指数退避自动重连。
- 内置约 15 个工具覆盖文献检索、论文分析、创新点、实验方案、服务器管理与命令执行；危险操作强制人工审批。
- 上下文自动压缩：接近模型上下文窗口 80% 时摘要精简早期历史，保证长任务可持续。
- 会话持久化（SQLite）：多会话管理、重命名、导出 Markdown、消息复制。
- 上下文用量圆环实时展示，超阈值变色预警。

### SSH 服务器自动化

- 服务器连接管理（密码/私钥认证）、连通性测试。
- 代码部署：服务器 git clone 或本地文件/文件夹 SFTP 上传。
- 结构化监控：GPU / CPU / 内存 / 磁盘 / 进程可视化展示。
- 浏览器内交互式终端（xterm.js + WebSocket，完整 TTY 体验）。

## 架构与技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 |
| 实时通信 | WebSocket（Agent 流式对话、Web 终端） |
| 后端 | Python + FastAPI（REST + WebSocket） |
| LLM 编排 | LangChain + `langchain-openai`（OpenAI 兼容 base_url） |
| 数据 | SQLite（元数据/历史）+ 本地文件（PDF/配置） |
| 文献抓取 | httpx（arXiv Atom API / Semantic Scholar Graph API）+ Playwright（百度学术/知网登录态） |
| 远程操作 | paramiko（SSH/SFTP） |

```
frontend (React)  ──HTTP──▶  backend (FastAPI)
       │                          │
       ├── WebSocket ──▶ Agent 流式循环（LangChain astream）
       │                    ├─ 工具层：搜索/下载/分析/创新点/实验/SSH/沙箱
       │                    └─ 会话持久化（SQLite）
       └── WebSocket ──▶ Web 终端（paramiko PTY）
```

## API

后端默认端口 8001，核心接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/search` | 关键词搜索（多平台聚合） |
| POST | `/api/search/topic` | AI 智能搜索（LLM 拆解主题） |
| POST | `/api/download` | 批量下载 PDF（后台任务+进度） |
| GET | `/api/papers` | 论文库查询 |
| POST/POST | `/api/papers/upload` · `/confirm` | 本地 PDF 上传 |
| GET/PUT | `/api/llm/config` | LLM 配置组（含代理设置） |
| POST | `/api/llm/test` · `/api/llm/models` | 连通性测试 / 拉取模型列表 |
| POST | `/api/analyze/{id}` · `/api/analyze/batch` | 单篇/批量论文分析 |
| POST | `/api/review` | 多篇对比综述 |
| POST/GET | `/api/innovations` · `/api/experiments` | 创新点 / 实验方案生成与历史 |
| CRUD | `/api/servers/*` | 服务器管理与部署 |
| POST | `/api/servers/{id}/monitor` | GPU/CPU/内存/磁盘监控 |
| WS | `/api/servers/{id}/terminal` | Web 终端 |
| WS | `/api/agent/ws` | Agent 流式对话（chat/approve/stop） |
| CRUD | `/api/agent/sessions*` | Agent 会话管理与导出 |
| CRUD | `/api/search/history*` | 搜索历史 |

## 配置

配置有三级优先级（高到低）：**界面保存**（`data/llm_config.json`，推荐）> 环境变量 > 内置默认。

环境变量（`.env.example` 有完整注释）：

| 变量 | 说明 |
|---|---|
| `SEMANTIC_SCHOLAR_API_KEY` | 可选。Semantic Scholar API Key，提高限流配额 |
| `HTTP_PROXY_OVERRIDE` | 可选。搜索/下载出站代理兜底（优先级低于界面代理设置） |
| `ARXIV_REQUEST_INTERVAL` / `ARXIV_MAX_RETRIES` | arXiv API 限速与重试 |
| `DOWNLOAD_MAX_RETRIES` / `DOWNLOAD_RETRY_DELAY` | PDF 下载重试 |

## 维护者

- 小洋 ([@shi-YangYang](https://github.com/shi-YangYang))

## 贡献

问题与反馈欢迎提交到 [GitHub Issue](https://github.com/shi-YangYang/openlab/issues)，接受 Pull Request。贡献前请阅读 [AGENTS.md](AGENTS.md) 了解开发流程与约定。

## 许可证

[MIT](LICENSE) © 小洋
