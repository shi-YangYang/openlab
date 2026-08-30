# openlab

<p align="center">
  <img src="docs/logo.png" alt="openlab logo" width="180" />
</p>

[简体中文](README.md) | **English**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/🦜🔗-LangChain-green.svg)](https://www.langchain.com/)
[![Electron](https://img.shields.io/badge/Electron-44-47848F.svg?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Ant Design](https://img.shields.io/badge/Ant%20Design-5-0170FE.svg?logo=antdesign&logoColor=white)](https://ant.design/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33.svg?logo=playwright&logoColor=white)](https://playwright.dev/)
[![WebSocket](https://img.shields.io/badge/WebSocket-realtime-orange.svg)](https://developer.mozilla.org/docs/Web/API/WebSocket)

Open-source research agent framework: literature mining → hypothesis generation → experiment design → SSH deployment, fully automated.

openlab puts the research workflow into a ready-to-use desktop workbench (Electron): multi-platform literature search and download, LLM-powered paper analysis and reviews, innovation-point and experiment-plan generation, plus a streaming conversational agent that orchestrates all of the above on its own — with one-click deployment to remote GPU servers (SSH + web terminal). The backend is bundled into the desktop client via PyInstaller; you can also run it from source.

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
4. **Deployment & execution** — one-click experiment execution on remote servers (env setup → background training → live logs), plus SSH management, GPU monitoring and web terminal.
5. **The Agent ties it all together** — state your research goal in natural language and the agent autonomously orchestrates every capability above.

The project follows spec-driven development (SDD) with a multi-agent workflow; the full evolution log lives in [specs/](specs/) and conventions in [AGENTS.md](AGENTS.md).

## Install

### Option 1: Download the installer (recommended)

Grab `openlab.Setup.<version>.exe` (Windows x64) from [Releases](https://github.com/shi-YangYang/openlab/releases/latest) and run the setup wizard.

- The installer bundles the Python runtime and all backend dependencies via PyInstaller — **no Python / Node.js required**.
- On launch, the Electron main process spawns the backend automatically with health checks and crash recovery; everything runs locally.
- Pushing a `v*` tag triggers GitHub Actions to build and publish the matching installer; the release notes list the commits included in that version.

### Option 2: Run from source

#### Prerequisites

- [Python](https://www.python.org/) 3.10+
- [Node.js](https://nodejs.org/) 18+
- Windows PowerShell (the one-click script is `.ps1`)

#### One-click start (Electron desktop client)

```powershell
cd openlab
.\start.ps1
```

The script detects and installs missing dependencies (Python venv, backend pip packages, Node/npm packages, electron), then starts the Electron desktop client (embedded frontend + auto-spawned backend).

#### Manual install (browser dev mode)

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
.\start.ps1                  # desktop client, backend 8001
.\start.ps1 -Port 9000       # custom backend port
npm run dev                  # dev mode: open http://localhost:5174 in a browser
```

The openlab desktop window opens automatically (in dev mode, open <http://localhost:5174> in a browser). Recommended first steps:

1. **Configure LLM**: Settings → "LLM 配置" → create a config group (pick a platform preset or enter an OpenAI-compatible Base URL + API Key) → fetch models → pick default model & reasoning effort → save. Multiple groups let you switch platforms anytime.
2. **Search literature**: use "直接搜索" (submit query as-is) or "AI 智能搜索" (LLM rewrites your topic into a precise query); select platforms and hit search, then batch-download results.
3. **Analyze papers**: click "分析" on downloaded papers to open the analysis page with structured results and Markdown export; multi-select for comparative reviews or innovation points.
4. **Use the Agent**: type a goal like “search attention-mechanism papers, download and analyze the top 2”; replies stream token by token, dangerous actions ask for confirmation in a modal, and long conversations are auto-compacted near the context limit.
5. **Generate experiment plans**: open an innovation record in history and click its experiment action; a structured plan (hypothesis/goal/datasets/baselines/metrics) is generated one-to-one.
6. **Run experiments**: in experiment-plan history click “执行” → pick a server → (edit step commands) → start. The pipeline runs sync-code → env-setup → background training with the training log streaming live; failures retry once then pause for manual fix (edit-retry / skip / abort). Or let the Agent drive the whole thing with one sentence.
7. **Connect servers** (optional): add SSH credentials → test connection → clone/upload code → view GPU monitoring or open the web terminal.

> If your machine cannot reach arXiv / Semantic Scholar directly (search failures or stuck downloads), set a proxy under Settings → "网络代理" (e.g. Clash's `127.0.0.1:7897`). Takes effect immediately after saving.

## Features

### Literature search & library

- Concurrent search across four platforms: arXiv, Semantic Scholar (official Graph API with automatic rate-limit retries), Baidu Xueshu, CNKI (browser login sessions).
- Two modes: direct keyword search and AI topic→query rewriting; result count, category and date filters.
- Batch PDF downloads with progress bars and status management; local storage, dedup, delete-with-cleanup.
- Local PDF upload with automatic metadata/source-link extraction and manual editing.

### LLM analysis

- Per-paper four-dimension structured analysis and multi-paper comparative review, bilingual (zh/en) with Markdown export.
- Innovation-point design with per-point one-to-one structured experiment-plan generation.
- Model config groups: manage multiple platform groups (OpenAI / DeepSeek / DashScope / SiliconFlow / Zhipu GLM / Moonshot Kimi…) and switch the active one anytime.
- Per-model context length and reasoning-effort options (built-in dictionary auto-fills common values when fetching models; always editable).

### Research agent

- WebSocket streaming chat: token-level output, real-time tool status, zero polling.
- Visual tool calls: collapsible parameter/result cards; failed calls expand by default.
- Full lifecycle control: one-click stop mid-run; exponential-backoff auto-reconnect on disconnect.
- 32 built-in tools covering literature retrieval, analysis, innovation, experiment execution, server management, platform login, command and code execution; dangerous operations force human approval.
- Automatic context compaction: history is summarized when usage crosses 80% of the model window, keeping long tasks alive.
- SQLite-persisted sessions: multi-session management, rename, Markdown export, message copy.
- Live context-usage ring that turns amber past the warning threshold.

### Automated experiment execution (dual-track)

- **Manual mode**: an execution panel drives the pipeline step by step (sync code → env setup → background training launch → output monitoring); every command is editable and skippable, training logs stream line-by-line with keyword filter and copy/download.
- **Agent mode**: start with one sentence (e.g. “run experiment plan yy on server xx”); the LLM derives env-setup and launch commands from the plan, asks for approval, then executes and reports progress on demand.
- Failure handling: each step retries once automatically, then pauses for human resolution (edit-and-retry / skip / abort).
- Process management: training runs via nohup with recorded PID; one-click stop (SIGTERM→SIGKILL) prevents runaway GPU usage; completion converges automatically with the full log persisted.
- Run history persisted with status/duration/error and log replay.

### SSH server automation

- Server management (password/key auth), connectivity tests.
- Deployment via server-side git clone or local file/folder SFTP upload.
- Structured monitoring: GPU / CPU / memory / disk / processes.
- In-browser interactive terminal (xterm.js over WebSocket, full TTY).

## Architecture & Tech Stack

| Layer | Technology |
|---|---|
| Desktop | Electron (spawns backend + health checks + crash recovery + frameless window) |
| Frontend | React 18 + TypeScript + Vite + Ant Design 5 |
| Realtime | WebSocket (agent streaming, web terminal) |
| Backend | Python + FastAPI (REST + WebSocket) |
| LLM orchestration | LangChain + `langchain-openai` (OpenAI-compatible base_url) |
| Data | SQLite (metadata/history) + local files (PDF/config) |
| Crawling | httpx (arXiv Atom API / Semantic Scholar Graph API) + Playwright (Baidu/CNKI login sessions) |
| Remote ops | paramiko (SSH/SFTP) |
| Packaging | PyInstaller (backend) + electron-builder (NSIS installer), auto-built & published by GitHub Actions on tags |

```
Electron main process (spawn backend / health check / crash restart / frameless window)
        │
frontend (React)  ──HTTP──▶  backend (FastAPI)
       │                          │
       ├── WebSocket ──▶ Agent streaming loop (LangChain astream)
       │                    ├─ tools: search/download/analysis/innovation/experiment-execution/SSH/sandbox
       │                    └─ session persistence (SQLite)
       ├── WebSocket ──▶ Experiment pipeline (step state machine + live logs)
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
| POST/GET | `/api/innovations` · `/api/experiments` | Innovation / experiment-plan generation & history (plans map 1:1 from innovation points) |
| CRUD+WS | `/api/experiment-runs*` | Experiment runs (create/start/live logs/retry/stop) |
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
