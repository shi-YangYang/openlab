# openlab backend

文献搜索与下载（arXiv）后端，基于 Python + FastAPI。

## 环境要求

- Python 3.10+

## 安装

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

（运行测试还需 `pip install -r requirements-dev.txt`）

## 配置

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 说明 | 默认值 |
| ---- | ---- | ---- |
| `LLM_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API Key（必须配置才能用主题拆解） | 空 |
| `LLM_MODEL` | 模型名 | `gpt-4o-mini` |
| `DATA_DIR` | 数据目录 | `backend/data` |
| `PAPERS_DIR` | PDF 存储目录 | `backend/data/papers` |
| `DB_PATH` | SQLite 路径 | `backend/data/openlab.db` |
| `ARXIV_REQUEST_INTERVAL` | arXiv 请求间隔（秒） | `3.0` |
| `ARXIV_MAX_RETRIES` | arXiv 重试次数 | `3` |
| `LLM_CONFIG_PATH` | 本地 LLM 配置文件路径 | `backend/data/llm_config.json` |

> API Key 只从本地配置文件 / 环境变量 / `.env` 读取，不硬编码、不入库。

### LLM 多平台配置

后端内置平台预设（`GET /api/llm/presets`），并支持自定义。前端「LLM 配置」区可下拉选择预设，自动填充 `base_url` / `model`，也可手动编辑并填写 `api_key`，保存后写入本地配置文件。

配置读取优先级（字段级）：**本地配置文件 > 环境变量 > 内置默认值**。

- 本地配置文件：`data/llm_config.json`（`data/` 已被 `.gitignore` 忽略，不入 git、不入 SQLite）。
- 环境变量：`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`（`.env` 亦可）。

常用 OpenAI 兼容 `base_url`：

| 平台 | base_url | 默认 model |
| ---- | ---- | ---- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 阿里云百炼 (DashScope) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 硅基流动 (SiliconFlow) | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| Moonshot Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

## 启动

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

服务地址：`http://localhost:8001`，交互式文档：`http://localhost:8001/docs`。

> 一键启动脚本 `start.ps1` 默认使用后端端口 8001，可通过 `-Port` 参数或 `OPENLAB_PORT` 环境变量配置（`-Port` 优先），前端代理端口与之一致。

## API

- `POST /api/search` — 关键词/检索式搜索 arXiv。
- `POST /api/search/topic` — 主题描述经 LLM 拆解后搜索。
- `POST /api/download` — 下载 PDF 全文（后台任务，异步执行）。
- `GET /api/papers` — 查询已下载论文元数据与状态。
- `GET /api/health` — 健康检查。
- `GET /api/llm/presets` — 查询 LLM 平台预设列表。
- `GET /api/llm/config` — 查询当前生效的 LLM 配置。
- `PUT /api/llm/config` — 保存 LLM 配置（base_url/api_key/model，写入本地非 git 文件）。
- `POST /api/analyze/{arxiv_id}` — 单篇论文结构化分析（后台任务）。
- `POST /api/analyze/batch` — 批量分析（异步逐篇）。
- `POST /api/review` — 多篇对比综述。
- `GET /api/analyses` — 查询分析结果列表（支持 `?arxiv_ids=` 过滤）。
- `GET /api/analyses/{arxiv_id}` — 查询单篇分析结果。
- `GET /api/analyses/{arxiv_id}/export` — 导出单篇分析 Markdown。
- `GET /api/reviews/{id}` — 查询综述结果。
- `GET /api/reviews/{id}/export` — 导出综述 Markdown。

## 测试

```powershell
cd ..
pytest
```
