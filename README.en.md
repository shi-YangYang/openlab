# openlab

[简体中文](README.md) | **English**

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

Open-source research agent framework: literature mining → hypothesis generation → experiment design → SSH deployment, fully automated.

openlab puts the research workflow into a single web workbench: multi-platform literature search and download, LLM-powered paper analysis and reviews, innovation-point and experiment-plan generation, plus a streaming conversational agent that orchestrates all of the above on its own — with one-click deployment to remote GPU servers (SSH + web terminal).

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Features](#features)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [API](#api)
- [Configuration](#configuration)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Security

- LLM API keys and SSH credentials are stored only in local config files (`backend/data/`, gitignored) — never hardcoded, never committed.
- Downloaded PDFs, the SQLite database and agent sessions live under `backend/data/` and never enter version control.
- Dangerous agent operations (remote commands, code execution, etc.) require explicit per-action user approval in the UI; tool outputs are automatically scrubbed of credentials.
- Never commit `.env` files or real secrets.

## Background

Researchers burn enormous time on repetitive work: searching literature, downloading PDFs, reading papers for reviews, brainstorming ideas, setting up environments and running experiments. openlab moves this pipeline into one unified interface:

1. **Literature mining** — search arXiv / Semantic Scholar / Baidu Xueshu / CNKI, download PDFs with visible progress, or upload your own.
2. **Paper understanding** — LLM-based structured analysis (problem/method/results/experiments), multi-paper comparative reviews.
3. **Hypothesis generation** — propose innovation points from selected papers, convert them into structured experiment plans in one click.
4. **Deployment** — SSH server management, git clone/SFTP deployment, GPU monitoring, interactive web terminal.
5. **The Agent ties it all together** — state your research goal in natural language and the agent autonomously orchestrates every capability above.

The project follows spec-driven development (SDD) with a multi-agent workflow; the full evolution log lives in [specs/](specs/) and conventions in [AGENTS.md](AGENTS.md).

## Install

### Prerequisites

- [Python](https://www.python.org/) 3.10+
- [Node.js](https://nodejs.org/) 18+
- Windows PowerShell (the one-click script is `.ps1`)

### One-click start

```powershell
cd openlab
.\start.ps1
```

The script detects and installs missing dependencies (Python venv, backend pip packages, Node/npm packages), then starts backend + frontend in one terminal.

### Manual install

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # optional: env-level configuration
uvicorn app.main:app --reload --port 8001

# Frontend
cd ..\frontend
npm install
npm run dev                  # http://localhost:5174
```

## Usage

```powershell
.\start.ps1                  # backend 8001, frontend 5174
.\start.ps1 -Port 9000       # custom backend port
```

Open <http://localhost:5174> and get started:

1. **Configure LLM**: Settings → "LLM 配置" → create a config group (pick a platform preset or enter an OpenAI-compatible Base URL + API Key) → fetch models → pick default model & reasoning effort → save. Multiple groups let you switch platforms anytime.
2. **Search literature**: use "直接搜索" (submit query as-is) or "AI 智能搜索" (LLM rewrites your topic into a precise query); select platforms and hit search, then batch-download results.
3. **Analyze papers**: click "分析" on downloaded papers to open the analysis page with structured results and Markdown export; multi-select for comparative reviews or innovation points.
4. **Use the Agent**: type a goal like “search attention-mechanism papers, download and analyze the top 2”; replies stream token by token, dangerous actions ask for confirmation in a modal, and long conversations are auto-compacted near the context limit.
5. **Connect servers** (optional): add SSH credentials → test connection → clone/upload code → view GPU monitoring or open the web terminal.

> If your machine cannot reach arXiv / Semantic Scholar directly (search failures or stuck downloads), set a proxy under Settings → "网络代理" (e.g. Clash's `127.0.0.1:7897`). Takes effect immediately after saving.

## Features

### Literature search & library

- Concurrent search across four platforms: arXiv, Semantic Scholar (official Graph API with automatic rate-limit retries), Baidu Xueshu, CNKI (browser login sessions).
- Two modes: direct keyword search and AI topic→query rewriting; result count, category and date filters.
- Batch PDF downloads with progress bars and status management; local storage, dedup, delete-with-cleanup.
- Local PDF upload with automatic metadata/source-link extraction and manual editing.

### LLM analysis

- Per-paper four-dimension structured analysis, multi-paper comparative review, innovation points, experiment plans — bilingual (zh/en) with Markdown export.
- Model config groups: manage multiple platform groups (OpenAI / DeepSeek / DashScope / SiliconFlow / Zhipu GLM / Moonshot Kimi…) and switch the active one anytime.
- Per-model context length and reasoning-effort options (built-in dictionary auto-fills common values when fetching models; always editable).

### Research agent

- WebSocket streaming chat: token-level output, real-time tool status, zero polling.
- Visual tool calls: collapsible parameter/result cards; failed calls expand by default.
- Full lifecycle control: one-click stop mid-run; exponential-backoff auto-reconnect on disconnect.
- ~15 built-in tools covering literature retrieval, analysis, innovation, experiments, server management and command execution; dangerous operations force human approval.
- Automatic context compaction: history is summarized when usage crosses 80% of the model window, keeping long tasks alive.
- SQLite-persisted sessions: multi-session management, rename, Markdown export, message copy.
- Live context-usage ring that turns amber past the warning threshold.

### SSH server automation

- Server management (password/key auth), connectivity tests.
- Deployment via server-side git clone or local file/folder SFTP upload.
- Structured monitoring: GPU / CPU / memory / disk / processes.
- In-browser interactive terminal (xterm.js over WebSocket, full TTY).

## Architecture & Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Ant Design 5 |
| Realtime | WebSocket (agent streaming, web terminal) |
| Backend | Python + FastAPI (REST + WebSocket) |
| LLM orchestration | LangChain + `langchain-openai` (OpenAI-compatible base_url) |
| Data | SQLite (metadata/history) + local files (PDF/config) |
| Crawling | httpx (arXiv Atom API / Semantic Scholar Graph API) + Playwright (Baidu/CNKI login sessions) |
| Remote ops | paramiko (SSH/SFTP) |

```
frontend (React)  ──HTTP──▶  backend (FastAPI)
       │                          │
       ├── WebSocket ──▶ Agent streaming loop (LangChain astream)
       │                    ├─ tools: search/download/analysis/innovation/experiment/SSH/sandbox
       │                    └─ session persistence (SQLite)
       └── WebSocket ──▶ Web terminal (paramiko PTY)
```

## API

Backend defaults to port 8001. Core endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/api/search` | Multi-platform keyword search |
| POST | `/api/search/topic` | AI search (LLM topic rewriting) |
| POST | `/api/download` | Batch PDF download (background jobs + progress) |
| GET | `/api/papers` | Paper library |
| POST/POST | `/api/papers/upload` · `/confirm` | Local PDF upload |
| GET/PUT | `/api/llm/config` | LLM config groups (incl. proxy setting) |
| POST | `/api/llm/test` · `/api/llm/models` | Connectivity test / list models |
| POST | `/api/analyze/{id}` · `/api/analyze/batch` | Single/batch paper analysis |
| POST | `/api/review` | Comparative review |
| POST/GET | `/api/innovations` · `/api/experiments` | Innovation / experiment generation & history |
| CRUD | `/api/servers/*` | Server management & deployment |
| POST | `/api/servers/{id}/monitor` | GPU/CPU/memory/disk monitoring |
| WS | `/api/servers/{id}/terminal` | Web terminal |
| WS | `/api/agent/ws` | Streaming agent chat (chat/approve/stop) |
| CRUD | `/api/agent/sessions*` | Agent session management & export |
| CRUD | `/api/search/history*` | Search history |

## Configuration

Three precedence levels (high → low): **UI-saved settings** (`data/llm_config.json`, recommended) > environment variables > built-in defaults.

Environment variables (fully commented in `.env.example`):

| Variable | Description |
|---|---|
| `SEMANTIC_SCHOLAR_API_KEY` | Optional. Raises the Semantic Scholar rate-limit quota |
| `HTTP_PROXY_OVERRIDE` | Optional. Fallback outbound proxy for search/download (lower priority than the UI proxy setting) |
| `ARXIV_REQUEST_INTERVAL` / `ARXIV_MAX_RETRIES` | arXiv API pacing and retries |
| `DOWNLOAD_MAX_RETRIES` / `DOWNLOAD_RETRY_DELAY` | PDF download retries |

## Maintainers

- 小洋 ([@shi-YangYang](https://github.com/shi-YangYang))

## Contributing

Issues and feedback are welcome at [GitHub Issues](https://github.com/shi-YangYang/openlab/issues); PRs are accepted. Please read [AGENTS.md](AGENTS.md) first for workflow conventions.

## License

[MIT](LICENSE) © 小洋
