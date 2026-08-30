# Spec 027 实施计划

## 批次划分（严格串行，每批次验证）

### 批次 1：后端 database.py → db 包

- 新建 `backend/app/db/` 包，按表拆分 CRUD。
- `db/__init__.py` re-export 全部公开函数（保持 `from .. import database` 兼容）。
- 原 database.py 删除（被 db 包替代）。
- 更新所有 import：`from . import database` → `from . import database`（不变，因为 db 包是 database.py 的替代）。
- 实际做法：`database.py` 改名为 `db/__init__.py`，CRUD 函数移入子模块，`__init__.py` re-export。
- 跑 pytest。

### 批次 2：后端 main.py → routes 包 + app.py

- 新建 `backend/app/routes/` 包，按业务域拆 APIRouter。
- 新建 `backend/app/app.py`（FastAPI 实例 + include_router）。
- 原 main.py 只保留 `app = ...` 的 re-export（uvicorn 启动入口 `app.main:app` 兼容）。
- 路由注册顺序严格保持现有顺序（`{arxiv_id:path}` 冲突问题）。
- 跑 pytest。

### 批次 3：前端样式重构

- `index.css` 提取公共类。
- AgentPage / ExperimentRunPanel / LlmConfigForm / TitleBar / ServerDetailPage 引入 `.module.css`。
- 跑 build。

### 批次 4：前端组件拆分

- AgentPage → `agent/` 目录 5 个子组件。
- ServerDetailPage → `server/` 目录 4 个子组件。
- ExperimentRunPanel → `experiment-run/` 目录 2 个子组件。
- LlmConfigForm → `llm-config/` 目录 2 个子组件。
- 跑 build。

### 批次 5：全量验证

- pytest 全量 + npm build 全量 + electron:dev 冒烟。
- 确认 NFR-4（单文件 ≤ 300 行）。

## 文件清单（关键变化）

### 后端
- 删除：`main.py`、`database.py`
- 新建：`app.py`、`routes/`（8 文件）、`db/`（8 文件）

### 前端
- 删除：`AgentPage.tsx`、`ServerDetailPage.tsx`、`ExperimentRunPanel.tsx`、`LlmConfigForm.tsx`
- 新建：`agent/`（5 文件）、`server/`（4 文件）、`experiment-run/`（2 文件）、`llm-config/`（2 文件）
- 新建：`*.module.css` 文件

### 修改
- `main.tsx`（BrowserRouter→HashRouter 已改，import 路径）
- `tests/`（import 路径 database → db）

## 验证方式

每批次完成后跑 pytest + npm build。最终全量 + electron:dev 冒烟。
