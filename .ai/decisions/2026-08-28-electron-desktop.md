# spec-026 Electron 桌面客户端决策

## 决策标题

确定 openlab 从 Web 应用迁移到 Electron 桌面客户端的架构方案：后端打包、启动方式与 UI 改造范围。

## 元信息

- **日期**：2026-08-28
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-026-electron-desktop

## 背景与问题

当前 openlab 是 Web 应用（FastAPI 后端 + React 前端），用户需要运行 start.ps1 打开终端再手动开浏览器。产品化需要：双击一个 exe 即可启动完整桌面客户端。

## 备选方案

- 方案 A：Electron 仅包装前端，Python 后端仍需用户手动安装/启动。
- 方案 B（采用）：后端也用 PyInstaller 打包成独立 exe，Electron 主进程启动时自动拉起后端 exe，实现真正的"双击即用"。

## 决策

1. **后端打包**：PyInstaller 将 FastAPI 后端打包为单个 `openlab-backend.exe`（one-dir 模式，含 pymupdf/playwright 等）。数据目录改为 exe 同级的 `data/`。
2. **Electron 主进程**：启动时 spawn 后端 exe → 轮询 health → 就绪后创建 BrowserWindow 加载前端。退出时终止后端进程。
3. **分发**：electron-builder 打 NSIS 安装包（.exe 安装向导），后端 exe 与前端静态资源一起打入安装包。
4. **UI 桌面化**：自定义标题栏（frameless + 最小化/关闭按钮），顶部导航改为左侧固定侧边栏（桌面应用风格），去掉浏览器相关交互。
5. **开发模式**：`npm run electron:dev` 同时启动后端（venv uvicorn）+ 前端 dev server + Electron，热更新保留。

## 理由

- 双击 exe 是用户明确的交付目标，PyInstaller one-dir 是 Python 桌面分发的标准做法。
- Electron 拉起后端进程是最成熟的 Python + Electron 混合架构（Jupyter 桌面版、ComfyUI 等均用此模式）。
- UI 桌面化改动保持最小——保留现有页面内容，只改导航容器与标题栏。

## 影响与后果

- 需新增 `electron/` 目录（main process + preload）与 electron-builder 配置。
- 后端路径全部从 `__file__` 相对改为可配置（PyInstaller 下 `__file__` 指向临时目录）。
- Playwright 浏览器二进制需在 PyInstaller spec 中显式收集，安装包体积会显著增大。
- WS/REST API 不变——前端只是从浏览器搬到 Electron 渲染进程。
