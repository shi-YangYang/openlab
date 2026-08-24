# 验收标准与验收记录：文献搜索与下载（arXiv）

## 验收标准

- AC-1（对应 FR-1）：输入关键词可返回 arXiv 搜索结果列表。
- AC-2（对应 FR-2）：输入主题描述，LLM 可拆解为检索式并返回结果。
- AC-3（对应 FR-3）：结果列表展示标题、作者、摘要、分类、日期、arXiv ID。
- AC-4（对应 FR-4）：可配置返回数量，支持分类与日期过滤。
- AC-5（对应 FR-5）：可下载 PDF 全文到本地目录。
- AC-6（对应 FR-6）：元数据入库 SQLite，重复下载被跳过。
- AC-7（对应 FR-7）：界面展示下载进度/状态。
- AC-8（对应 NFR-1）：API Key 不入库、不硬编码。
- AC-9（对应 FR-8）：LLM 层基于 LangChain ChatOpenAI，自定义 base_url 生效。
- AC-10（对应 FR-9）：后端提供平台预设接口，前端可下拉选择预设并可自定义 base_url/model/key。
- AC-11（对应 FR-10）：LLM 配置持久化到本地非 git 文件，密钥不入库、不硬编码。
- AC-12（对应 FR-11）：运行 `start.ps1` 能检测/安装缺失依赖并启动前后端，日志合并展示，后端默认端口 8001（可通过参数/环境变量自定义）且前端代理与之一致，后端 `/api/health` 与前端页面可访问。

## 验收步骤

1. 启动后端（和前端）。
2. 用关键词搜索，验证结果列表。
3. 用主题描述搜索，验证 LLM 拆解与结果。
4. 配置数量/分类/日期过滤，验证生效。
5. 触发 PDF 下载，验证本地目录生成文件、SQLite 有元数据。
6. 重复下载验证跳过。
7. 运行 pytest 测试通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 14 个 pytest 全部通过；真实启动后端冒烟通过（/api/health、/api/search、/api/download、去重跳过）；前端 npm run build 通过。LLM 真实调用因未配置 LLM_API_KEY 未实测（代码路径经 mock 验证）。 | 通过，可进入下一环节 |
| 2 | 2026-08-24 | PASS | 补充实施 FR-8~10 / AC-9~11 验收通过。25 个 pytest 全部通过（新增 11 个：llm LangChain 层、presets、llm_config 持久化）；前端 npm run build 通过（3036 modules）；`GET /api/llm/presets` 真实返回 6 平台；`GET/PUT /api/llm/config` 真实读写 data/llm_config.json（经 .gitignore `data/` 规则忽略）；SQLite 无密钥列；全仓无硬编码密钥。AC-1~8 无回归。 | 通过，可进入下一环节 |
| 3 | 2026-08-24 | BLOCKED | AC-12（FR-11）静态验证全部满足：`start.ps1` 正确检测 Python/Node/npm 且缺失时清晰报错（含安装指引 URL）；幂等（`backend\.venv`、后端依赖 import 检测、`frontend\node_modules`、根 `node_modules` 均有存在性判断）；无硬编码密钥；未改动 backend/frontend 业务代码（start.ps1/根 package.json 为新增根文件，仅调用既有脚本）。根 package.json Windows 命令引号/路径正确（实际运行 `cd backend && .venv\Scripts\python.exe -m uvicorn ...` 与 `cd frontend && npm run dev` 均成功启动，concurrently 日志含 `[backend]`/`[frontend]` 前缀）。但完整端到端运行被阻塞：后端 uvicorn 绑定 8000 失败（WinError 10013），因 Docker Desktop（com.docker.backend.exe PID 21804）已占用 127.0.0.1:8000，concurrently --kill-others 随之终止前端。独立验证：后端改 8001 端口 `/api/health` 返回 200 `{"status":"ok"}`；前端 vite 返回 200 且含 `<div id="root">`。 | 阻塞为外部端口冲突（Docker 占 8000），非脚本缺陷。需协调开发 Agent 决策：更换默认后端端口或要求用户释放 8000 后复验 |
| 4 | 2026-08-24 | PASS | AC-12（FR-11 端口返工）验收通过。默认端口 8001：`start.ps1:16` `[int]$Port = 8001`、`frontend/vite.config.ts:10` 代理回退 `process.env.OPENLAB_PORT \|\| 8001`；优先级 `-Port` > `OPENLAB_PORT` > 默认（`start.ps1:22-24`）正确；后端经 `%OPENLAB_PORT%`（根 `package.json:8`，实测展开为 `--port 9000`）、前端代理经 `process.env.OPENLAB_PORT` 指向同一端口。PowerShell 5.1 `Parser::ParseFile` 无语法错误；`start.ps1` 为 UTF-8 BOM（EF BB BF）。端到端实测 `.\start.ps1 -Port 9000`：后端监听 127.0.0.1:9000、`/api/health`→`{"status":"ok"}`、经 vite 代理 `/api/health`→ok、前端根 200 含 `<div id="root">`；`$env:OPENLAB_PORT=8901; .\start.ps1`（无 -Port）后端监听 8901 且代理一致。pytest 25 passed、前端 `npm run build` 通过。无硬编码 8000（仅 `App.tsx:31` `Date.now()+180000` 子串，无关）、无硬编码密钥；未改动业务代码（git 仅跟踪 LICENSE，FR-11 产物为新增/未跟踪文件）。Docker 仍占 127.0.0.1:8000 与 127.0.0.1:5173（IPv4），但因默认已改 8001、vite 绑定 ::1:5173（IPv6）双栈共存，端到端未受影响。 | 通过，AC-12 满足，可进入下一环节 |

## 验收结论

**PASS（轮次 4 / AC-12 端口返工）** —— AC-1 ~ AC-11 已通过（轮次 1、2）；本轮针对轮次 3 的 BLOCKED（Docker 占用 8000）完成端口返工并验收通过：默认端口改为 8001，支持 `-Port` 参数与 `OPENLAB_PORT` 环境变量（优先级 `-Port` > 环境变量 > 默认），后端与前端代理端口一致。端到端实测 `-Port 9000` 与 `OPENLAB_PORT=8901` 均正常启动、`/api/health` 与前端代理可访问。详见下方轮次 4 逐条判定。

### 轮次 4 逐条判定与证据（AC-12 端口返工）

- **默认端口 8001：PASS**。`start.ps1:16` `param([int]$Port = 8001)`；`frontend/vite.config.ts:10` 代理 `target: http://localhost:${process.env.OPENLAB_PORT || 8001}`。全仓无残留硬编码 8000（唯一命中为 `frontend/src/App.tsx:31` `Date.now() + 180000` 的字符串子串，与端口无关）。
- **优先级 -Port > 环境变量 > 默认：PASS**。`start.ps1:22-24` `if (-not $PSBoundParameters.ContainsKey('Port') -and $env:OPENLAB_PORT) { $Port = [int]$env:OPENLAB_PORT }`，随后 `$env:OPENLAB_PORT = "$Port"`。逻辑正确：传 `-Port` 时忽略环境变量；未传且设环境变量时采用环境变量；均未提供时用默认 8001。
- **后端经 %OPENLAB_PORT%、前端代理经 process.env.OPENLAB_PORT：PASS**。根 `package.json:8` `dev:backend` 为 `... --reload --port %OPENLAB_PORT%`（运行时实测展开为 `--port 9000`，见进程命令行）；`vite.config.ts:10` 代理目标随 `process.env.OPENLAB_PORT` 变化。
- **PowerShell 5.1 可解析：PASS**。`[System.Management.Automation.Language.Parser]::ParseFile(...)` 无语法错误；`start.ps1` 首字节 `EF BB BF`（UTF-8 BOM）。
- **端到端实测：PASS**。见下方「实际运行情况」。
- **未改动业务代码：PASS**。`git ls-files` 仅 `LICENSE`；FR-11 相关文件（`start.ps1`、根 `package.json`、`package-lock.json`、`frontend/vite.config.ts`）均为新增/未跟踪文件，未编辑 backend/frontend 业务逻辑（搜索/下载/LLM/配置）。`vite.config.ts` 的改动仅限代理端口，属 FR-11 预期范围。
- **无硬编码密钥：PASS**。`backend/app`、`frontend/src` 及全仓（排除 node_modules/.venv/data）grep `sk-...`/`api_key = "..."` 均无命中。

### 实际运行情况（轮次 4）

- 后端：`python -m pytest` → **25 passed**（0.48s）。
- 前端：`npm run build`（`tsc && vite build`）→ **构建成功**（3036 modules，6.30s；仅 chunk 体积告警，非错误）。
- 场景 A（`.\start.ps1 -Port 9000`）：Python 3.11.2 / node v24.9.0 / npm 11.6.0 检测通过；依赖步骤幂等跳过；concurrently 合并输出含 `[backend]`/`[frontend]` 前缀；后端 uvicorn `Running on http://127.0.0.1:9000`；`GET http://127.0.0.1:9000/api/health` → 200 `{"status":"ok"}`；`GET http://localhost:5173/api/health`（vite 代理）→ 200 `{"status":"ok"}`；`GET http://localhost:5173/` → 200 且含 `<div id="root">`。验证后 taskkill 清理进程树。
- 场景 B（`$env:OPENLAB_PORT=8901; .\start.ps1`，无 `-Port`）：后端监听 127.0.0.1:8901，`/api/health` → 200 `{"status":"ok"}`，vite 代理 `/api/health` → 200 `{"status":"ok"}`。验证后清理。
- 环境注意：Docker Desktop（PID 21804）仍占用 127.0.0.1:8000 与 127.0.0.1:5173（IPv4）。因默认端口已改 8001，且 vite 在本机绑定 `::1:5173`（IPv6 回环）与 Docker 的 IPv4 5173 双栈共存，端到端未产生端口冲突，故不再构成阻塞。

---

以下为轮次 3 的历史记录（AC-12 端口返工前）：

### 逐条判定与证据

- **AC-1（FR-1，关键词搜索）：PASS**。真实启动后端后 `POST /api/search`（`query="attention transformer"`, `max_results=2`）返回 2 条真实 arXiv 结果（2209.15001、2605.26355）。单测 `tests/test_api.py:6` `test_search_returns_results` 通过。
- **AC-2（FR-2，主题 LLM 拆解）：PASS（代码级）**。`/api/search/topic` 实现在 `backend/app/main.py:80`，`decompose_topic` 在 `backend/app/llm.py:36`（OpenAI 兼容 `/chat/completions`）。单测 `tests/test_api.py:36`（mock 拆解）通过；未配置 Key 时正确返回 400（`test_search_topic_without_api_key`）。真实 LLM 调用因无 `LLM_API_KEY` 未实测（外部条件）。
- **AC-3（FR-3，结果字段展示）：PASS**。前端 `PaperTable.tsx` 展示标题/作者/分类/日期/arXiv ID，摘要经展开行展示；后端 `Paper` 含全部字段，`test_search_returns_results` 断言字段齐全。
- **AC-4（FR-4，数量/分类/日期过滤）：PASS**。`max_results` 有 `ge=1, le=100` 约束（`schemas.py:26`）；分类经 `_build_params` 生成 `cat:`（`arxiv.py:48`）；日期过滤在 `main.py:48`。单测 `test_search_filters_by_category_and_date` 通过。
- **AC-5（FR-5，PDF 下载到本地）：PASS**。真实下载 1706.03762，生成 `backend/data/papers/1706.03762.pdf`（2215244 字节）。实现 `downloader.py:18`。
- **AC-6（FR-6，元数据入库 + 去重跳过）：PASS**。SQLite `papers` 表含 spec 全部字段（`database.py:8`），`arxiv_id UNIQUE`；真实重复下载返回 `accepted=[]`、`skipped=["1706.03762"]`。单测 `test_database.py` 与 `test_download_and_skip_duplicate` 通过。
- **AC-7（FR-7，下载进度/状态）：PASS**。前端 `App.tsx:29` 轮询状态、`PaperTable.tsx:5` 状态列展示 pending/downloading/downloaded/failed。
- **AC-8（NFR-1，API Key 不入库/不硬编码）：PASS**。`papers` 表无任何含 `key` 的列（`test_no_api_key_column_in_schema`）；全仓 grep 无硬编码密钥；Key 仅从环境变量读取（`config.py:41`）；`.gitignore` 排除 `.env`、`.env.*`。
- **AC-9（FR-8，LangChain ChatOpenAI + 自定义 base_url）：PASS**。`backend/app/llm.py:10` `from langchain_openai import ChatOpenAI`；`llm.py:56-61` 构造 `ChatOpenAI(base_url=..., api_key=..., model=...)` 并 `ainvoke`，base_url 取自 `get_effective_config()`（`llm_config.py:82-93`），自定义 base_url 生效。`requirements.txt:6-7` 含 `langchain>=0.3`、`langchain-openai>=0.2`。单测 `tests/test_llm.py:22` `test_decompose_topic_uses_langchain_chatopenai` 断言 `base_url="https://api.deepseek.com/v1"` 等参数被正确传入。
- **AC-10（FR-9，平台预设接口 + 前端下拉/自定义）：PASS**。`presets.py:13-44` 内置 6 平台（OpenAI、DeepSeek、阿里云百炼、硅基流动、智谱 GLM、Moonshot Kimi）；`main.py:132-134` `GET /api/llm/presets` 返回该列表。前端 `LlmConfigForm.tsx:67-98` 平台 `Select`（含「自定义」）下拉选择后自动填充 base_url/model，并允许手动编辑 base_url/model/api_key（`Input.Password`）。实测 `GET /api/llm/presets` 返回 6 项。
- **AC-11（FR-10，配置持久化到本地非 git 文件）：PASS**。`llm_config.py:60-79` `save_config` 写入 `data/llm_config.json`（非 SQLite）；`.gitignore:15` `data/` 规则使其不入 git（`git check-ignore` 确认命中）；密钥仅存本地文件/环境变量，不入库（`database.py:8-22` schema 无密钥列）、不硬编码（grep 全仓 app 代码无真实密钥）、不打印日志（app 目录无 print/logging）。单测 `tests/test_llm_config.py` 覆盖 save/load/优先级/端点/落盘不入库。
- **AC-12（FR-11，一键启动脚本）：BLOCKED（静态 PASS，端到端被外部阻塞）**。
  - **脚本逻辑（静态，全部满足）**：`start.ps1:28-33` 检测 Python（缺失报错含安装 URL）；`:39-46` 幂等创建 `backend\.venv`；`:50-58` import 检测（fastapi/uvicorn/langchain_openai）失败才 `pip install -r requirements.txt`；`:62-71` 检测 Node/npm（缺失清晰报错）；`:77-90` 幂等安装 `frontend\node_modules`；`:94-107` 幂等安装根 `node_modules`（concurrently）；`:113-118` `npm run dev` 合并启动。根 `package.json` 用 `concurrently --kill-others --names backend,frontend --prefix-colors blue,green`，`dev:backend` 为 `cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`，`dev:frontend` 为 `cd frontend && npm run dev`。
  - **无硬编码密钥**：`start.ps1` / 根 `package.json` 无密钥；全仓 grep 仅测试文件出现假密钥（`sk-abc`/`sk-local`）。
  - **未改动业务代码**：FR-11 产物为新增根文件 `start.ps1`、`package.json`、`package-lock.json`，仅调用既有脚本，未编辑 `backend/`、`frontend/` 下任何文件（git 基线仅 `LICENSE`，其余均未跟踪，无法用 diff 对比，但经文件审查确认 FR-11 为纯新增根文件）。
  - **实际运行（被阻塞）**：真实执行 `.\start.ps1` → Python 3.11.2 / node v24.9.0 / npm 11.6.0 检测通过；各安装步骤因已存在全部跳过（幂等）；concurrently 启动并合并输出，日志含 `[backend]`/`[frontend]` 前缀；前端 vite `ready in 551ms` 绑定 5173。但后端 uvicorn 绑定 8000 失败 `[WinError 10013]`，因 Docker Desktop（`com.docker.backend.exe` PID 21804）已占用 127.0.0.1:8000；`--kill-others` 随之终止前端。**阻塞为外部端口冲突，非脚本缺陷**。
  - **独立复核（解除端口冲突后等价验证）**：后端改 8001 端口独立运行，`GET /api/health` → 200 `{"status":"ok"}`；前端 vite 独立运行，`GET http://localhost:5173/` → 200 且含 `<div id="root">`。证明脚本所启动的前后端本身可正常访问。

### 附加 NFR 检查

- **NFR-2（arXiv 限速）**：`arxiv.py` 实现请求间隔 + 指数退避重试（`interval`/`max_retries`），满足。
- **NFR-3（单用户无鉴权）**：无鉴权逻辑，满足。

### 测试实际运行情况

- 后端：`python -m pytest` → **25 passed**（0.36s；新增 11 个测试覆盖 llm LangChain 层、presets、llm_config 持久化）。
- 前端：`npm run build`（`tsc && vite build`）→ **构建成功**（3036 modules，5.56s；仅 chunk 体积告警，非错误）。
- 冒烟：TestClient 实测 `GET /api/llm/presets` 返回 6 平台；`GET /api/llm/config` 初始返回默认值；`PUT /api/llm/config` 写入后 `GET` 可读回（base_url/api_key/model 均生效），配置落盘至 `llm_config.json`。

### 发现的问题 / 阻塞项

1. **（阻塞项，轮次 3）** 后端默认端口 8000 被 Docker Desktop（`com.docker.backend.exe`，PID 21804）占用，导致 `start.ps1` 完整端到端运行时后端 uvicorn 绑定失败（WinError 10013）、`--kill-others` 终止前端。属外部环境冲突，非脚本缺陷；需协调开发 Agent 决策：更换默认后端端口，或要求用户释放 8000 后复验。
2. 真实 LLM 集成未实测——需真实 `LLM_API_KEY`（外部条件），非阻塞；LangChain 调用路径已通过 mock 验证。
3. 前端构建产物 chunk 偏大（1.13 MB，gzip 357 KB）——性能告警，不影响功能。
4. `GET /api/llm/config` 会明文返回 `api_key`（单用户本地场景，用于回填表单；NFR-3 无鉴权，可接受）。

### 结论

AC-1 ~ AC-11 满足（轮次 1、2）；AC-12（FR-11）脚本逻辑静态验证满足，但完整端到端运行被 Docker Desktop 占用端口 8000 阻塞，**本轮判定 BLOCKED**。脚本本身正确，待端口冲突解除（换端口或释放 8000）后即可复验通过。
