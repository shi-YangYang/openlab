# 实施计划：SSH 服务器部署与监控（spec-008）

## 任务拆分

1. 服务器配置存储（本地 `data/servers.json`）+ CRUD + 脱敏。
2. SSH 连接封装（paramiko）：连接、执行命令、SFTP。
3. 测试连接接口。
4. 代码部署：git clone + SFTP 递归上传。
5. 监控：执行 nvidia-smi/free/df/ps 等命令并返回结果。
6. 前端「服务器」页（列表/增删改/测试/部署/监控）。
7. 测试。

## 实施顺序

存储 → SSH 封装 → 测试连接 → 部署 → 监控 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/`（新增 servers 存储模块 + ssh 模块，扩展 main/schemas）。
- `frontend/src/`（新增服务器页组件，扩展 App 导航、api/types）。
- `tests/` 新增 SSH 相关测试（用 mock paramiko）。
- `backend/requirements.txt` 新增 paramiko。

## 技术要点

- 服务器配置存 `data/servers.json`（复用 settings.data_dir，已被 gitignore），读写类似 llm_config。
- paramiko SSHClient：连接 + exec_command + SFTPClient。
- 部署 clone：`git clone <repo_url> <target_dir>`；上传：SFTP 递归遍历本地目录上传到 remote_path。
- 监控：依次执行 `nvidia-smi`、`free -h`、`df -h`、`uptime`、`ps aux --sort=-%mem | head`，返回 {命令: 原始输出}。
- 凭据脱敏：列表/读取接口不返回 password/private_key，只返回是否已配置。
- 测试用 mock（不真实连接服务器）。

## 风险与应对

- nvidia-smi 无 GPU 或格式差异：容错处理，返回原始输出。
- 上传大目录：递归 + 错误处理。
