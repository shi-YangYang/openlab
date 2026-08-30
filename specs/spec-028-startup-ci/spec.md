# Spec：启动方式改造与 CI/CD（spec-028）

## 元信息

- **Spec 编号**：`spec-028-startup-ci`
- **状态**：`draft`
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-startup-ci.md`
- **负责人**：协调开发 Agent

## 背景与动机

1. start.ps1 仍启动浏览器模式，与 Electron 桌面客户端定位不符。
2. 安装包打包仅在开发机手动执行 `npm run electron:build`，需要 tag 触发自动打包。

## 目标

- start.ps1 双击运行 = Electron 桌面客户端启动。
- push tag `v*` 时 GitHub Actions 自动构建 NSIS 安装包并上传到 GitHub Release。

## 范围

### 包含（In Scope）

- start.ps1 改造为 Electron 开发模式启动。
- `.github/workflows/release.yml` tag 触发自动打包。
- Release 上传。

### 不包含（Out of Scope）

- macOS / Linux CI。
- 自动版本号（从 tag 提取，需手动同步 package.json version）。
- Playwright 浏览器打包（保持现状）。

## 需求描述

### 功能需求

- FR-1：`start.ps1` 改造：保留依赖检测（Python/venv/Node/npm/concurrently/electron），最终启动命令从 `npm run dev` 改为 `npm run electron:dev`。
- FR-2：新增 `.github/workflows/release.yml`：
  - `on: push: tags: ['v*']`
  - `runs-on: windows-latest`
  - steps：
    1. checkout
    2. setup Python 3.12（cache pip）→ `pip install -r backend/requirements.txt pyinstaller`
    3. setup Node 20（cache npm）→ `npm install`（根目录含 electron/electron-builder）→ `cd frontend && npm install && npm run build`
    4. PyInstaller：`cd backend && .venv\Scripts\python.exe -m PyInstaller openlab_backend.spec --noconfirm`
    5. electron tsc：`frontend\node_modules\.bin\tsc.cmd -p electron/tsconfig.json`
    6. electron-builder：`npx electron-builder --win`（env ELECTRON_MIRROR + HTTP_PROXY 可选）
    7. Create Release：softprops/action-gh-release，上传 `frontend/dist_electron/*.exe`
- FR-3：Release body 自动生成（从 tag 间的 commit log）。

### 非功能需求

- NFR-1：CI 不要求 secrets（公开仓库 release 写入用 `GITHUB_TOKEN`，GitHub 自动提供）。
- NFR-2：Playwright 浏览器不打包（保持现状，安装包 ~467MB）。
- NFR-3：CI 总耗时目标 < 20 分钟。

## 依赖与前置条件

- GitHub Actions 免费额度（公开仓库无限制）。
- npm 依赖下载需网络（可设 `ELECTRON_MIRROR` 环境变量加速）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- CI 中 PyInstaller 可能遇到 hiddenimports 缺失（开发机 venv 与 CI 环境差异），需迭代。
- electron/electron-builder 下载在 CI 可能慢，可用 `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` 加速。
