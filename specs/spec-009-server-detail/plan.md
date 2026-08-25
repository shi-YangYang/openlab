# 实施计划：服务器详情页与监控可视化（spec-009）

## 任务拆分

1. 后端：结构化监控解析（nvidia-smi --query-gpu 解析、free/df/uptime/ps 解析，容错回退 raw）。
2. 后端：执行命令接口 `POST /api/servers/{id}/exec`。
3. 后端：部署上传支持 multipart 文件上传（浏览器选择文件 → 后端 SFTP）。
4. 前端：一级服务器列表四个操作 + 二级详情页（面包屑 + 路由状态）。
5. 前端：详情页监控可视化（GPU 表格/进度条、内存/磁盘进度、负载）。
6. 前端：部署功能区（手动路径 + 文件/文件夹选择器）+ 环境配置（预设+自定义命令执行）。
7. 测试。

## 实施顺序

后端结构化监控 → exec → 上传 → 前端详情页 → 可视化 → 部署/环境配置 → 测试。

## 涉及文件/模块

- `backend/app/`（新增 monitor 解析模块，扩展 main/schemas/servers/ssh）。
- `frontend/src/`（新增 ServerDetailPage 等，重构 ServersPage，扩展 api/types）。
- `tests/` 新增监控解析、exec、上传测试。

## 技术要点

- GPU 解析：`nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits`，解析失败回退 `nvidia-smi` 原始文本。
- 内存 `free -m`、磁盘 `df -h`、负载 `cat /proc/loadavg`、进程 `ps aux --sort=-%mem | head`，逐项解析+容错。
- exec：复用 ssh.exec_command，返回 {output}。
- 上传：multipart（FastAPI UploadFile）→ 临时目录 → SFTP；保留本地路径方式。
- 前端详情页：状态内切换 list/detail（不引入 react-router，用 state + 面包屑）。

## 风险与应对

- 解析格式差异：try/except + 回退 raw。
- 大文件上传：流式 + 超时提示。
