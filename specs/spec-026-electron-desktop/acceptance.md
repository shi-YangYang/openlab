# Spec 026 验收清单

## AC-1 开发模式（FR-10）

- [ ] `npm run electron:dev`：Electron 窗口自动打开，后端自动启动，页面正常加载。
- [ ] 前端热更新生效（修改代码后页面自动刷新）。
- [ ] 关闭 Electron 窗口后后端进程同步退出（无残留 uvicorn）。

## AC-2 PyInstaller 后端 exe（FR-4 / FR-5 / FR-6）

- [ ] `dist/openlab-backend/openlab-backend.exe` 双击可运行。
- [ ] `/api/health` 返回 200。
- [ ] 数据目录在 exe 同级 `data/` 下自动创建。
- [ ] 搜索/分析/翻译等核心功能正常（pymupdf 可导入）。

## AC-3 自定义标题栏（FR-3 / FR-7）

- [ ] Electron 窗口无系统标题栏，显示自定义标题栏（logo + openlab + 最小化/关闭按钮）。
- [ ] 拖拽标题栏可移动窗口。
- [ ] 最小化/关闭按钮正常工作；关闭后后端进程终止。
- [ ] 浏览器开发模式（无 Electron）不显示标题栏。

## AC-4 侧边栏导航（FR-8）

- [ ] 左侧固定侧边栏（约 200px），菜单项垂直排列，当前路由高亮。
- [ ] 点击各菜单项路由正常跳转。
- [ ] Content 区域占剩余宽度，无横向溢出。

## AC-5 NSIS 安装包（FR-9）

- [ ] `npm run electron:build` 产出 `.exe` 安装包。
- [ ] 安装向导：可选择安装目录，完成后桌面快捷方式创建。
- [ ] 双击桌面快捷方式启动完整客户端（后端自动拉起、页面加载正常）。
- [ ] 卸载后无残留进程。

## AC-6 回归

- [ ] 后端 `pytest tests -q` 全部通过（286+）。
- [ ] 前端 `npm run build` 通过。
- [ ] 搜索/分析/翻译/创新点/实验/Agent/服务器 全流程正常。
