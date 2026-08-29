# Spec 026 实施计划

## 批次划分

### 批次 0：基础设施安装

- npm：`npm install -D electron electron-builder`（根目录）。
- pip：`backend\.venv\Scripts\pip install pyinstaller`。

### 批次 1：后端 PyInstaller 打包 + 路径改造

- `backend/app/config.py`：frozen 路径检测。
- `backend/main_entry.py`：PyInstaller 入口（uvicorn.run 不带 reload）。
- `backend/openlab_backend.spec`：PyInstaller spec。
- 打包测试：`dist/openlab-backend/openlab-backend.exe` 可独立运行，`/api/health` 200。
- Playwright 浏览器收集。

### 批次 2：Electron 主进程

- 根目录 `electron/main.ts`、`electron/preload.ts`。
- 后端进程管理（spawn / health poll / kill tree）。
- BrowserWindow（frameless）+ IPC（minimize/quit/backendPort）。
- `package.json` main 字段 + scripts。

### 批次 3：前端桌面化

- `main.tsx`：Electron 检测 + 标题栏渲染。
- `App.tsx`：Menu 从水平改为垂直侧边栏；Content 布局调整。
- `index.css`：标题栏 drag 区域样式。
- preload 暴露的 `window.electronAPI` 类型声明。

### 批次 4：electron-builder 打包

- `electron-builder.yml` 配置。
- `package.json` build 字段。
- `npm run electron:build` 完整流程（PyInstaller → vite → electron-builder）。
- 产出 NSIS 安装包。

## 文件清单

### 新建
- `electron/main.ts`
- `electron/preload.ts`
- `frontend/src/components/TitleBar.tsx`
- `frontend/src/components/ErrorBoundary.tsx`（已有）
- `frontend/src/types/electron.d.ts`
- `backend/main_entry.py`
- `backend/openlab_backend.spec`
- `electron-builder.yml`

### 修改
- `package.json`（main、scripts、devDeps）
- `backend/app/config.py`（frozen 路径）
- `frontend/src/main.tsx`（ErrorBoundary + TitleBar）
- `frontend/src/App.tsx`（侧边栏布局）
- `frontend/src/index.css`（drag 样式）
- `frontend/vite.config.ts`（base 路径，Electron 用 file:// 加载）

## 验证方式

- `pytest tests -q`：后端回归（无破坏）。
- `npm run build`：tsc + vite 编译通过。
- `npm run electron:dev`：Electron 窗口启动、后端自动拉起、页面正常。
- `npm run electron:build`：产出 NSIS 安装包，安装后双击快捷方式启动正常。
