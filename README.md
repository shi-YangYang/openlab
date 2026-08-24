# openlab

Open-source research agent framework: literature mining, hypothesis generation, experiment design, and SSH deployment.

openlab is an open-source research agent framework that automates the scientific research workflow end-to-end: it searches and downloads papers, analyzes them, proposes research hypotheses and innovations, designs experiments, and deploys them to remote GPU servers over SSH.

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Features](#features)
- [API](#api)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Security

- LLM API keys are read from configuration (a local config file or environment variables) and are never hardcoded or committed to the repository.
- The `data/` directory (downloaded PDFs, SQLite database, and `llm_config.json`) is gitignored.
- Do not commit `.env` files or any credentials.

## Background

openlab frees researchers from repetitive work by automating the full research pipeline:

1. **Literature mining** — search and download papers from arXiv.
2. **Hypothesis generation** — analyze papers and propose research hypotheses and innovations.
3. **Experiment design** — turn hypotheses into executable experiment plans.
4. **SSH deployment** — deploy and monitor experiments on remote GPU servers.

The project follows a Spec-Driven Development (SDD) process with a multi-agent collaboration workflow. See [AGENTS.md](AGENTS.md).

## Install

### Prerequisites

- [Python](https://www.python.org/) 3.10+
- [Node.js](https://nodejs.org/) 18+

### One-click start (Windows PowerShell)

```powershell
cd openlab
.\start.ps1
```

The script detects and installs missing dependencies (Python virtualenv, backend `pip` packages, Node/npm packages), then starts the backend and frontend with merged output.

### Manual setup

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # fill in LLM_API_KEY etc.
uvicorn app.main:app --reload --port 8001

# Frontend
cd ..\frontend
npm install
npm run dev                  # http://localhost:5173
```

## Usage

```powershell
.\start.ps1                  # backend on 8001, frontend on 5173
.\start.ps1 -Port 9000       # custom backend port
$env:OPENLAB_PORT=9000; .\start.ps1
```

Open http://localhost:5173 in your browser.

- **Keyword search** — enter a query (e.g. `attention transformer`) and filter by category and date; works without an LLM key.
- **Topic search** — enter a research topic; the LLM decomposes it into an arXiv query. Requires configuring an LLM platform and API key in the UI (or via `PUT /api/llm/config`).
- **Download** — select papers and download their PDFs to `backend/data/papers/`; metadata is stored in SQLite with deduplication.

## Features

- arXiv search by keyword/query and by topic (LLM-decomposed).
- Configurable result count, category and date filtering.
- PDF download with progress/status, local storage, and deduplication.
- LLM orchestration via LangChain (`ChatOpenAI` with a custom `base_url`), OpenAI-compatible.
- Built-in LLM platform presets (OpenAI, DeepSeek, Alibaba DashScope, SiliconFlow, Zhipu GLM, Moonshot Kimi) plus custom configuration.

## API

The backend exposes the following endpoints (default port 8001):

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/search` | Keyword/query search on arXiv |
| POST | `/api/search/topic` | Topic search (LLM decomposition) |
| POST | `/api/download` | Download PDFs (background task) |
| GET | `/api/papers` | List downloaded papers |
| GET | `/api/llm/presets` | LLM platform presets |
| GET/PUT | `/api/llm/config` | Read/save LLM configuration |

## Maintainers

- 小洋 ([@shi-YangYang](https://github.com/shi-YangYang))

## Contributing

Questions and issues are welcome at the [GitHub issue tracker](https://github.com/shi-YangYang/openlab/issues). Pull requests are accepted. Before contributing, please read [AGENTS.md](AGENTS.md) for the development process and conventions.

## License

[MIT](LICENSE) © 小洋
