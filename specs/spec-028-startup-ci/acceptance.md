# Spec 028 验收清单

## AC-1 start.ps1 改造（FR-1）

- [ ] 运行 `.\start.ps1`：依赖检测后启动 Electron 窗口（非浏览器）。
- [ ] 前端热更新正常。
- [ ] 关闭窗口后后端进程终止。

## AC-2 CI/CD tag 打包（FR-2 / FR-3）

- [ ] push tag `v*` 时 GitHub Actions 自动运行。
- [ ] 构建成功后 Release 页面出现 NSIS 安装包。
- [ ] 下载安装包安装后可正常启动。

## 回归

- [ ] `pytest tests -q` 全部通过；`npm run build` 通过。
