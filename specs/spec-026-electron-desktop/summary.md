# Spec 026 总结

## 元信息

- **Spec 编号**：`spec-026-electron-desktop`
- **状态**：completed（已完成）
- **创建日期**：2026-08-28
- **关联决策**：`.ai/decisions/2026-08-28-electron-desktop.md`

## 目标

openlab 从 Web 应用迁移到 Electron 桌面客户端：双击安装包安装、桌面快捷方式启动、Python 后端自动拉起。

## 需求清单与实现

| FR | 内容 | 结果 |
|---|---|---|
| FR-1 | Electron 主进程（spawn 后端/health 轮询/端口递增/崩溃重启循环/kill 进程树） | ✅ |
| FR-2 | preload（contextBridge 暴露 getInfo/minimize/quit/apiOrigin） | ✅ |
| FR-3 | 自定义标题栏（frameless、drag 区域、最小化/关闭 IPC） | ✅ |
| FR-4 | PyInstaller spec（one-dir、langchain/pymupdf/playwright 全量收集） | ✅ |
| FR-5 | config.py frozen 路径检测（exe 同级 data 目录） | ✅ |
| FR-6 | backend/main_entry.py（uvicorn 无 reload 入口） | ✅ |
| FR-7 | 前端 Electron 检测（window.electronAPI 条件渲染） | ✅ |
| FR-8 | App.tsx 侧边栏（Sider 200px 垂直菜单 + Content 占余宽） | ✅ |
| FR-9 | electron-builder NSIS 安装包配置 | ✅ |
| FR-10 | electron:dev / electron:build scripts | ✅ |

## 验收结果

- 实施（含一轮返工）：后端 **292 passed**；前端 build 通过；Electron tsc 编译通过。
- 打包产物：
  - PyInstaller 后端 exe：`backend/dist/openlab-backend/openlab-backend.exe`（20.2 MB，目录 1101 MB 含 Playwright 浏览器）
  - NSIS 安装包：`frontend/dist_electron/openlab Setup 0.1.0.exe`（**466.9 MB**，含 chromium）
- 验收：返工后 3 项全部 **PASS**（TitleBar 单点渲染、崩溃重启循环、Playwright/pymupdf 打包）；总体通过。

## 决策引用

- `.ai/decisions/2026-08-28-electron-desktop.md`

## 使用方式

### 开发模式
```powershell
npm run electron:dev    # 后端(reload) + 前端(vite) + Electron 窗口
```

### 打包
```powershell
npm run electron:build  # PyInstaller → vite build → NSIS 安装包
```
产出：`frontend/dist_electron/openlab Setup 0.1.0.exe`

## 遗留问题

- Playwright 浏览器未预下载到干净机器——需首次运行联网下载（或后续 spec 改为预打包）。
- 安装到 Program Files 时非管理员运行 SQLite/PDF 写入可能失败（建议装到用户目录，后续可改 %APPDATA%）。
- PyInstaller exe 可能被 Windows Defender 误报（文档建议加白名单）。
- 重启递归分支存在空转路径（非阻塞，后续顺手清理）。
