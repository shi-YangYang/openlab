# Spec：Electron 桌面客户端（spec-026）

## 元信息

- **Spec 编号**：`spec-026-electron-desktop`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-electron-desktop.md`
- **负责人**：协调开发 Agent

## 背景与动机

openlab 当前是 Web 应用，需要终端运行 start.ps1 + 手动开浏览器。产品化目标是：用户双击一个安装包安装后，桌面双击快捷方式即可启动完整桌面客户端（Electron 窗口内嵌前端 + 自动拉起 Python 后端）。

## 目标

- Electron 桌面客户端（Windows），双击快捷方式启动。
- 后端 PyInstaller 打包为独立 exe，Electron 自动拉起/关闭。
- UI 桌面化：自定义标题栏 + 左侧固定导航。
- electron-builder 打 NSIS 安装包。

## 范围

### 包含（In Scope）

- Electron 主进程 + preload 脚本 + electron-builder 配置。
- PyInstaller 打包后端为 one-dir exe。
- 后端路径改造：支持 PyInstaller frozen 环境。
- UI 桌面化：自定义标题栏（frameless）、侧边栏导航。
- 开发模式保留（electron:dev 热更新）。

### 不包含（Out of Scope）

- macOS / Linux 打包。
- 自动更新（auto-update）。
- 系统托盘。
- UI 完全重设计。

## 需求描述

### 功能需求

#### Electron 主进程

- FR-1：`electron/main.ts`：
  - `app.whenReady()` → spawn 后端 exe（开发模式 spawn venv uvicorn --reload）→ 轮询 `http://localhost:{port}/api/health`（每 500ms，最多 30s）→ 创建 BrowserWindow（1280×800，frameless，icon 为 logo.ico）加载前端。
  - `app.on('window-all-closed')` → kill 后端进程树 → `app.quit()`。
  - 后端崩溃自动重启（最多 3 次）。
  - 端口：默认 8001，被占用则递增（8002, 8003…），通过 IPC 传给前端。
- FR-2：`electron/preload.ts`：通过 `contextBridge` 暴露 `window.electronAPI = { backendPort, platform, quit, minimize }`。
- FR-3：自定义标题栏：BrowserWindow `frameless: true` + `titleBarStyle: 'hidden'`；前端渲染标题栏（logo + app 名 + 最小化/关闭按钮），拖拽区域 `-webkit-app-region: drag`。IPC 调 minimize/close。

#### 后端 PyInstaller

- FR-4：`backend/openlab.spec`（PyInstaller spec 文件）：
  - one-dir 模式，输出 `dist/openlab-backend/`。
  - `collect_data_files` 收纳 pymupdf、langchain 等的数据文件。
  - Playwright：`collect_all` playwright 包 + 在 spec 中指定浏览器二进制路径（`PLAYWRIGHT_BROWSERS_PATH=0` 一起打包）。
  - hidden imports：uvicorn 的 worker、langchain 的子模块。
- FR-5：后端路径改造（`config.py`）：
  - 判断 `getattr(sys, 'frozen', False)`：frozen 时 `BASE_DIR = Path(sys.executable).parent`（exe 同级目录），数据目录 `BASE_DIR / data`。
  - 非 frozen（开发模式）保持现有 `__file__` 相对逻辑不变。
- FR-6：后端启动入口：新增 `backend/main.py`（或 `backend/__main__.py`）作为 PyInstaller entry point，启动 uvicorn（不含 --reload）。

#### UI 桌面化

- FR-7：前端检测 Electron 环境（`window.electronAPI`）：
  - 渲染自定义标题栏：左侧 logo + app 名，右侧最小化/关闭按钮（IPC 调用），整条 `-webkit-app-region: drag`。
  - 非 Electron（浏览器开发模式）不渲染标题栏，保持现有布局。
- FR-8：导航改造：顶部水平 Menu 改为左侧垂直 Menu（固定 200px 宽侧边栏，顶部放标题栏，下方放菜单项）。Content 区域占剩余宽度。
- FR-9：electron-builder 配置（`electron-builder.yml`）：
  - appId、productName=openlab、icon=docs/logo.ico。
  - `extraResources`：将 `dist/openlab-backend/`（PyInstaller 输出）整体打入安装包 resources。
  - NSIS：oneClick=false（安装向导）、allowToChangeInstallationDirectory=true、桌面快捷方式。

#### 开发模式

- FR-10：`package.json` 新增：
  - `electron:dev`：concurrently 启动后端（venv uvicorn --reload）+ 前端 vite + electron（加载 http://localhost:5174）。
  - `electron:build`：先 PyInstaller 打后端 → vite build 前端 → electron-builder 打安装包。

### 非功能需求

- NFR-1：安装包体积：不含 Playwright 浏览器二进制时目标 < 500MB（Playwright chromium ~300MB 额外）。
- NFR-2：冷启动到前端可见 ≤ 10 秒（后端 health 轮询就绪后加载）。
- NFR-3：退出时后端进程完整终止（进程树 kill，防止僵尸 uvicorn）。
- NFR-4：现有全部 API / WS 端点不变，前端代码仅改标题栏与导航布局。
- NFR-5：`pytest tests -q` 与 `npm run build` 通过；`npm run electron:dev` 可正常启动。

## 数据结构约定

- Electron 目录：`electron/main.ts`、`electron/preload.ts`。
- PyInstaller spec：`backend/openlab_backend.spec`。
- 后端 exe 输出：`backend/dist/openlab-backend/openlab-backend.exe`。
- 打包输出：`frontend/dist_electron/`。

## 依赖与前置条件

- 新增 npm devDependencies：electron、electron-builder、concurrently（已有）。
- 新增 pip devDependency：pyinstaller。
- PyInstaller 需在 venv 中安装（开发机），不加入 requirements.txt（用户手动安装时不需要）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- **PyInstaller 隐蔽导入**：langchain/langchain-openai 依赖链深，可能出现运行时 ModuleNotFoundError，需在 spec 的 hiddenimports 中逐个补充（迭代解决）。
- **Playwright 浏览器打包**：chromium ~300MB，安装包总体积可能 > 800MB。若不可接受可改为首次运行时下载浏览器（需网络）。
- **杀毒软件误报**：PyInstaller exe 可能被 Windows Defender 误报，用户需加白名单（文档说明）。
- **venv 与 PyInstaller 冲突**：PyInstaller 需在 venv 内运行以正确收集依赖。
