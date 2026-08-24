# openlab frontend

文献搜索与下载（arXiv）前端，基于 React + TypeScript + Vite + Ant Design。

## 环境要求

- Node.js 18+

## 安装与启动

```powershell
cd frontend
npm install
npm run dev
```

开发服务器默认运行在 `http://localhost:5174`，并通过 Vite 代理将 `/api` 转发到
`http://localhost:8001`（后端）。请确保后端已启动。

代理目标端口读取环境变量 `OPENLAB_PORT`（未设置时默认 8001）。使用一键启动脚本
`start.ps1` 时，端口由脚本统一解析（`-Port` 参数 > `OPENLAB_PORT` 环境变量 > 默认 8001），
前后端自动保持一致。

## 构建

```powershell
npm run build
```
