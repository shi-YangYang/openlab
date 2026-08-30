# spec-028 启动方式改造与 CI/CD 决策

## 决策标题

确定 start.ps1 改造为 Electron 启动、GitHub Actions CI/CD 自动打包（tag 触发）的方案。

## 元信息

- **日期**：2026-08-28
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-028-startup-ci

## 背景与问题

1. start.ps1 仍启动浏览器模式（终端+浏览器），与 Electron 桌面客户端定位不符。
2. 安装包打包（pyinstaller → frontend build → electron-builder）仅在开发机手动执行，需要 CI/CD 自动化：push tag（如 `v0.2.0`）时 GitHub Actions 自动打包并上传安装包到 GitHub Release。

## 决策

1. **start.ps1 改造**：改为启动 Electron 开发模式（等同于 `npm run electron:dev`），不再启动浏览器模式。保留依赖检测与自动安装逻辑。
2. **CI/CD**：新增 `.github/workflows/release.yml`：
   - 触发：push tag `v*`
   - 步骤：checkout → setup Python（venv + pip install requirements + pyinstaller）→ setup Node（npm install + frontend build）→ PyInstaller 打包后端 → electron-builder 打 NSIS 安装包 → 上传到 GitHub Release
   - runner：`windows-latest`
3. **打包命令**：`npm run electron:build`（已有），确认可用。

## 理由

- start.ps1 定位从浏览器模式改为 Electron 模式，与产品最终形态一致。
- GitHub Actions tag 触发是标准的版本发布流程，无需自建 CI 服务器。

## 影响与后果

- `.github/workflows/release.yml` 新增。
- start.ps1 中浏览器启动逻辑替换为 electron:dev。
- Playwright 浏览器在 CI 中不打包（保持现状，安装包 ~467MB），如需打包后续 spec。
- Release 页面将出现安装包 artifact。
