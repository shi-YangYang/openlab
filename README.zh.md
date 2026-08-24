# openlab

开源科研 Agent 框架：文献挖掘、假设生成、实验设计、SSH 服务器部署自动化。

openlab 是一个开源科研 Agent 框架，将科研流程全自动化：自动搜索并下载论文、分析论文、提出科研假设与创新点、设计实验，并通过 SSH 部署到远程 GPU 服务器运行。

## 目录

- [安全](#安全)
- [背景](#背景)
- [安装](#安装)
- [使用](#使用)
- [特性](#特性)
- [API](#api)
- [维护者](#维护者)
- [贡献](#贡献)
- [许可证](#许可证)

## 安全

- LLM API Key 从配置读取（本地配置文件或环境变量），绝不硬编码、不入库。
- `data/` 目录（下载的 PDF、SQLite 数据库、`llm_config.json`）已被 gitignore。
- 禁止提交 `.env` 文件或任何凭据。

## 背景

openlab 通过自动化科研全流程，把科研人员从重复劳动中解放出来：

1. **文献挖掘** — 从 arXiv 搜索并下载论文。
2. **假设生成** — 分析论文并提出科研假设与创新点。
3. **实验设计** — 将假设转化为可执行的实验方案。
4. **SSH 部署** — 在远程 GPU 服务器上部署与监控实验。

项目遵循规格驱动开发（SDD）与多 Agent 协作工作流，详见 [AGENTS.md](AGENTS.md)。

## 安装

### 前置依赖

- [Python](https://www.python.org/) 3.10+
- [Node.js](https://nodejs.org/) 18+

### 一键启动（Windows PowerShell）

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
copy .env.example .env      # 填写 LLM_API_KEY 等
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
$env:OPENLAB_PORT=9000; .\start.ps1
```

浏览器打开 http://localhost:5174。

- **关键词搜索** — 输入检索词（如 `attention transformer`），支持分类与日期过滤；无需 LLM Key。
- **主题搜索** — 输入研究主题，由 LLM 拆解为 arXiv 检索式；需在界面配置 LLM 平台与 API Key（或 `PUT /api/llm/config`）。
- **下载** — 勾选论文下载 PDF 到 `backend/data/papers/`；元数据入库 SQLite 并去重。

## 特性

- 支持关键词/检索式搜索，以及主题（LLM 拆解）搜索 arXiv。
- 可配置返回数量、分类与日期过滤。
- PDF 下载带进度/状态、本地存储与去重。
- 基于 LangChain 的 LLM 编排（`ChatOpenAI` 自定义 `base_url`，OpenAI 兼容）。
- 内置 LLM 平台预设（OpenAI、DeepSeek、阿里云百炼、硅基流动、智谱 GLM、Moonshot Kimi）+ 自定义。

## API

后端默认端口 8001，接口如下：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/search` | 关键词/检索式搜索 arXiv |
| POST | `/api/search/topic` | 主题搜索（LLM 拆解） |
| POST | `/api/download` | 下载 PDF（后台任务） |
| GET | `/api/papers` | 查询已下载论文 |
| GET | `/api/llm/presets` | LLM 平台预设 |
| GET/PUT | `/api/llm/config` | 读取/保存 LLM 配置 |

## 维护者

- 小洋 ([@shi-YangYang](https://github.com/shi-YangYang))

## 贡献

问题与反馈欢迎提交到 [GitHub Issue](https://github.com/shi-YangYang/openlab/issues)，接受 Pull Request。贡献前请阅读 [AGENTS.md](AGENTS.md) 了解开发流程与约定。

## 许可证

[MIT](LICENSE) © 小洋
