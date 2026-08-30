# Spec：代码重构——样式系统与大文件模块化（spec-027）

## 元信息

- **Spec 编号**：`spec-027-refactor`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-refactor.md`
- **负责人**：协调开发 Agent

## 背景与动机

1. 前端累计 **212 处行内样式**，大量重复（width:100% × 16、marginBottom × 18、居中模式 × 9 等），无法复用、无法媒体查询、无设计 token。
2. **前端大文件**：AgentPage.tsx 1176 行（最大的单文件组件）、ServerDetailPage 551 行、ExperimentRunPanel 539 行、LlmConfigForm 522 行。
3. **后端大文件**：main.py 1631 行（71 个 REST/WS 端点全在一个文件）、database.py 1058 行（全部表的 CRUD）。

## 目标

- 公共样式提取到 CSS，行内样式数量减少 80%+。
- AgentPage/ServerDetailPage/ExperimentRunPanel/LlmConfigForm 拆为子组件。
- 后端 main.py 拆为 APIRouter、database.py 拆为 db 包。

## 范围

### 包含（In Scope）

- 公共 CSS 类提取（全局 index.css）+ CSS Modules 按需引入。
- 前端 4 个大文件拆分为子组件。
- 后端 main.py 拆为 APIRouter、database.py 拆为 db 包。

### 不包含（Out of Scope）

- types.ts / api.ts 拆分（体量尚可）。
- styled-components / TailwindCSS 引入。
- 后端 schemas.py 拆分。
- 新功能开发。

## 需求描述

### 前端样式重构

- SR-1：全局 `index.css` 提取公共 CSS 类：
  - `.text-secondary-12`（fontSize:12 + secondary 色）
  - `.page-center`（textAlign:center + padding）
  - `.code-block`（深色底等宽字体）
  - `.log-area`（日志区深色底）
  - `.file-chip`（附件 chip 样式）
  - `.section-title`（Typography.Title level=5 替代）
- SR-2：AgentPage / ExperimentRunPanel / LlmConfigForm / TitleBar / ServerDetailPage 引入对应 `.module.css`，行内样式迁移到模块类。

### 前端组件拆分

- SR-3：AgentPage.tsx（1176 行）→ `agent/` 目录：
  - `AgentPage.tsx`（组合入口，~100 行）
  - `AgentChatMessages.tsx`（消息气泡 + 工具卡片 + 流式渲染，~200 行）
  - `AgentChatInput.tsx`（输入框 + 附件拖拽 + 工具行，~180 行）
  - `AgentApprovalModal.tsx`（审批弹窗，~80 行）
  - `AgentSessionList.tsx`（会话列表 + 重命名 + 导出，~150 行）
- SR-4：ServerDetailPage.tsx → `server/` 目录：MonitorSection / DeploySection / ExecSection / TerminalSection 四个文件。
- SR-5：ExperimentRunPanel.tsx → `experiment-run/` 目录：CreateView / RunView 两个文件。
- SR-6：LlmConfigForm.tsx → `llm-config/` 目录：GroupList / GroupForm 两个文件。

### 组件化标准（所有拆分组件必须遵循）

每个拆出的组件文件必须按以下固定结构编写（自上而下）：

```
1. imports（第三方 → 本项目类型 → 本项目组件/hooks/工具，用空行分组）
2. 常量（STATUS_META 等映射表，放组件外部）
3. 类型定义（Props interface / 本地 interface）
4. 工具函数（纯函数，组件外部）
5. 子组件（如有，先声明）
6. 主组件 export default function
   - hooks（useState/useEffect/useCallback/useRef，按声明顺序）
   - 派生变量（const 计算）
   - 事件处理函数（handle* 命名）
   - return JSX
7. 子组件/辅助函数（如 export function paperActionColumn）
```

规则：
- **Props 接口命名**：`{ComponentName}Props`
- **状态提升**：多个子组件共享的状态提升到父组件，通过 props 传递；子组件不直接调用 API（由父组件或 hooks 层处理）
- **hooks 抽取**：跨组件复用的逻辑（如轮询、WS 连接）抽为自定义 hook 放 `hooks/` 目录
- **常量抽取**：跨组件复用的映射表/枚举放 `constants.ts` 或组件文件顶部 export
- **样式**：组件私有样式放 `{ComponentName}.module.css`，公共样式放 index.css；不使用行内样式（动态值用 CSS 变量传入）
- **事件命名**：`handle{Action}`；props 回调命名：`on{Event}`
- **导出方式**：组件用 `export default function {Name}()`；非组件工具用 named export

### 后端拆分

- SR-7：main.py（1631 行）→ `routes/` 包（APIRouter）：
  - `routes/papers.py`（搜索/下载/论文库/翻译 ~200 行）
  - `routes/agent.py`（WS + 会话 CRUD + 附件 ~200 行）
  - `routes/servers.py`（服务器 CRUD/部署/监控/终端 WS ~180 行）
  - `routes/experiments.py`（实验方案/运行/WS ~180 行）
  - `routes/llm.py`（配置/模型/测试 ~100 行）
  - `routes/platforms.py`（平台登录 ~60 行）
  - `routes/search.py`（搜索/历史 ~80 行）
  - `routes/innovations.py`（创新点 ~80 行）
  - `app.py`（app 实例 + include_router + CORS + lifespan，~50 行）
- SR-8：database.py（1058 行）→ `db/` 包：
  - `db/__init__.py`（_connect/_migrate/init_db，re-export 全部公开函数）
  - `db/papers.py`、`db/agent.py`、`db/experiments.py`、`db/search_history.py`、`db/innovations.py`、`db/reviews.py`、`db/experiment_runs.py`

### 后端模块化标准

每个 routes/ 文件必须按以下结构编写：

```
1. imports（标准库 → 第三方 → 本项目，用空行分组）
2. router = APIRouter()
3. 依赖注入函数 / 共享 helper（如 _require_server）
4. 端点函数（按 HTTP 方法分组：GET → POST → PUT → DELETE → WS）
5. 端点级 helper（仅在文件内使用的函数）
```

规则：
- **router 前缀**：在 include_router 时设置 prefix，端点内不重复写完整路径
- **响应模型**：所有端点必须声明 response_model（WS 除外）
- **错误处理**：统一 HTTPException(status_code, detail)，不在端点内 try-except 吞异常
- **db 调用**：端点只调用 database/db 层函数，不直接写 SQL
- **模块导入**：延迟导入（函数内 import）仅用于避免循环依赖，其余放文件顶部

### 非功能需求

- NFR-1：拆分后 `pytest tests -q` 全部通过（import 路径变更不破坏测试）。
- NFR-2：`npm run build` 通过；CSS Modules 类名不影响 antd 组件。
- NFR-3：`npm run electron:dev` 正常启动。
- NFR-4：拆分后单文件 ≤ 300 行（AgentPage 入口 ≤ 100 行）。
- NFR-5：不做任何功能性变更——纯重构，行为完全一致。
- NFR-6：所有拆分组件/模块遵循上述组件化标准格式，验收时逐文件检查结构合规性。

## 数据结构约定

- CSS Modules 命名：`{ComponentName}.module.css`，与组件同目录。
- 后端 routes 包：`backend/app/routes/`，每个文件一个 APIRouter 实例。
- db 包：`backend/app/db/`，`__init__.py` re-export 保持 `from .. import database` 兼容。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- main.py 拆分后路由顺序可能变化（`{arxiv_id:path}` 贪婪匹配问题——需确保 translation/pdf 在 /pdf 之前的顺序保留）。
- CSS Modules 与 antd 的 className 冲突（antd 用全局类名，module 用 hash 类名，理论上不冲突）。
- 测试文件 import 路径需同步更新（database → db 等）。
