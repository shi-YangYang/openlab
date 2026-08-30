# Summary：spec-028-startup-ci

## 完成日期

2026-08-30

## 实施内容

### 1. start.ps1 改造（Electron 启动）

- 启动命令从 `npm run dev`（浏览器模式）改为 `npm run electron:dev`（Electron 桌面客户端）。
- 依赖检测链保留并扩展：Python/venv → Node/npm → 根目录 `npm install`（含 electron、concurrently）→ `frontend npm install` → PyInstaller 检测 → 启动。

### 2. `.github/workflows/release.yml`（tag 触发 CI/CD）

- 触发条件：`push: tags: ['v*']`，`runs-on: windows-latest`，`permissions: contents: write`。
- 构建步骤：checkout → Python 3.12（pip cache）→ backend 依赖 + PyInstaller → Node 20（npm cache）→ 根/前端 npm install → 前端 vite build → PyInstaller 打包后端 → tsc 编译 Electron 主进程 → electron-builder NSIS 打包（`--publish never`）→ softprops/action-gh-release 上传 `frontend/dist_electron/*.exe`。
- 关键修复（CI 迭代 3 次）：
  1. **v1 失败**：electron-builder 步骤报 `exit code 1`，匿名 API 无法读日志 → 增加 `Tee-Object` 落盘日志 + 失败时上传 artifact。
  2. **v2 失败根因**：tag 触发导致 electron-builder **隐式启用 GitHub 发布流程**，要求 `GH_TOKEN` 而未设置（`Implicit publishing triggered by git tag`）。构建本身已成功。
  3. **v3 修复**：`npx electron-builder --win --publish never`，发布统一交给 softprops 步骤（使用 GitHub 自动注入的 `GITHUB_TOKEN`，无需配置 secrets）。构建成功。

## 验证结果

- GitHub Actions run（commit `6f4cc41`）：**success**，总耗时约 12 分钟（< 20 分钟目标）。
- Release `v0.2.0` 自动创建，产物 `openlab.Setup.0.1.0.exe`（172.7 MB）已上传，可公开下载。

## 交付物

- `start.ps1`：Electron 启动模式。
- `.github/workflows/release.yml`：tag 自动打包 + Release 发布。

## 遗留事项

- 安装包版本号 `0.1.0` 取自根 `package.json`，与 tag `v0.2.0` 不同步（spec 明确 Out of Scope，需手动维护）。
- 签名使用 electron-builder 自签/未签名流程，无代码签名证书（未在 spec 范围内）。
- macOS / Linux CI 未覆盖（Out of Scope）。
