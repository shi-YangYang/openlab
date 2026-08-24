# Spec：SSH 服务器部署与监控（spec-008）

## 元信息

- **Spec 编号**：`spec-008-ssh-deploy-monitor`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-ssh-deploy.md`
- **负责人**：协调开发 Agent

## 背景与动机

实验设计（spec-007）产出方案后，需要把代码部署到远程 GPU 服务器运行。spec-008 实现 SSH 服务器连接管理、代码部署与服务器监控，为后续自动跑实验打基础。

## 目标

- 管理 SSH 服务器连接（增删改查 + 测试连接），凭据存本地配置。
- 代码部署：SFTP 上传本地文件、服务器 git clone。
- 服务器监控：查看 GPU/CPU/内存/磁盘/进程状态。
- 前端提供「服务器」页面进行管理、部署与监控。

## 范围

### 包含（In Scope）

- 服务器连接管理（CRUD + 测试连接）。
- 代码部署（SFTP 上传 + git clone）。
- 服务器监控（GPU/CPU/内存/磁盘/进程）。
- 前端「服务器」导航页。

### 不包含（Out of Scope）

- 自动跑实验与结果回传（后续 spec）。
- 多级 SSH 跳板、堡垒机等高级连接。

## 需求描述

### 功能需求

- FR-1：服务器连接管理（增删改查），凭据存本地配置文件（不入库、不入 git）。
- FR-2：测试服务器 SSH 连接，返回成功/失败与耗时。
- FR-3：服务器列表展示（凭据脱敏，不返回密码/私钥）。
- FR-4：代码部署 - 服务器上执行 git clone（输入 repo_url、target_dir）。
- FR-5：代码部署 - SFTP 上传本地文件/目录到服务器（输入 local_path、remote_path，递归上传）。
- FR-6：服务器监控 - 返回 GPU、CPU、内存、磁盘、进程状态（执行 nvidia-smi / free / df / ps 等命令）。
- FR-7：前端「服务器」页面：服务器列表、添加/编辑/删除、测试连接、部署、监控。

### 非功能需求

- NFR-1：SSH 用 paramiko 实现。
- NFR-2：凭据安全（不入库、不打印日志、API 响应脱敏）。
- NFR-3：SSH 连接与命令执行带超时与错误处理。

## 数据结构约定

服务器配置（本地 JSON `data/servers.json`）：

```json
{
  "id": "string",
  "name": "string",
  "host": "string",
  "port": 22,
  "username": "string",
  "auth_type": "password" | "key",
  "password": "string",
  "private_key": "string"
}
```

## 后端接口草案

- `GET /api/servers` — 服务器列表（脱敏）。
- `POST /api/servers` — 新增服务器。
- `PUT /api/servers/{id}` — 更新服务器。
- `DELETE /api/servers/{id}` — 删除服务器。
- `POST /api/servers/{id}/test` — 测试连接。
- `POST /api/servers/{id}/deploy/clone` — git clone（repo_url, target_dir）。
- `POST /api/servers/{id}/deploy/upload` — SFTP 上传（local_path, remote_path）。
- `POST /api/servers/{id}/monitor` — 监控（GPU/CPU/内存/磁盘/进程）。

## 依赖与前置条件

- Python + FastAPI 后端。
- paramiko 依赖。
- 本地文件存储（复用 `data/`，已被 gitignore）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- nvidia-smi 解析格式因服务器/驱动而异，监控以原始输出为主。
- 大文件/目录上传耗时，需进度或超时提示。
