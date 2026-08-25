# Spec：服务器详情页与监控可视化（spec-009）

## 元信息

- **Spec 编号**：`spec-009-server-detail`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-server-detail.md`、`.ai/decisions/2026-08-24-ssh-deploy.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-008 已能管理服务器、部署、监控（返回原始命令文本）。spec-009 优化交互：新增服务器二级详情页，把监控可视化、部署增强、环境配置等能力整合进去。

## 目标

- 服务器二级详情页（面包屑导航）。
- 监控可视化：GPU/CPU/内存/磁盘用表格/进度条/卡片展示。
- 部署增强：本地路径支持手动输入 + 文件/文件夹选择器。
- 环境配置：预设命令 + 自定义命令执行。

## 范围

### 包含（In Scope）

- 一级页每服务器四个操作（编辑/详情/删除/测试）+ 二级详情页。
- 结构化监控（GPU/CPU/内存/磁盘/进程）+ 可视化展示。
- 部署：文件/文件夹选择器上传 + 手动路径。
- 环境配置：预设命令模板 + 自定义命令执行并展示输出。

### 不包含（Out of Scope）

- Web 终端（spec-010）。
- 自动跑实验（后续 spec）。

## 需求描述

### 功能需求

- FR-1：一级服务器列表每服务器有「编辑」「详情」「删除」「测试」四个操作。
- FR-2：二级服务器详情页，顶部面包屑「服务器列表 / 服务器名」。
- FR-3：详情页顶部监控可视化（GPU 表格/利用率进度条、CPU 负载、内存/磁盘进度，替代原始文本）。
- FR-4：监控返回结构化数据（GPU 列表、内存、磁盘、负载、进程），解析失败回退原始输出。
- FR-5：部署功能区：本地路径支持手动输入 + 文件/文件夹选择器（浏览器选择文件上传）。
- FR-6：环境配置：预设命令（如 pip install -r requirements.txt、conda 相关）+ 自定义命令执行。
- FR-7：命令执行结果在界面展示（输出文本）。

### 非功能需求

- NFR-1：复用 paramiko。
- NFR-2：凭据安全沿用（不入库、不打印、脱敏）。
- NFR-3：监控解析容错（无 GPU、命令不存在、格式差异时回退原始输出）。

## 数据结构约定

结构化监控（示意）：

```json
{
  "gpu": [{"index": 0, "name": "A100", "utilization": 85, "memory_used_mb": 20000, "memory_total_mb": 80000}],
  "load": [1.2, 0.8, 0.5],
  "memory": {"used_mb": 32000, "total_mb": 256000},
  "disk": [{"filesystem": "/dev/sda1", "size": "1T", "used": "500G", "use_percent": 50, "mount": "/"}],
  "processes": ["..."],
  "raw": {}
}
```

## 后端接口草案

- `GET /api/servers/{id}` — 单服务器（脱敏）。
- `POST /api/servers/{id}/monitor` — 结构化监控（含 raw 回退）。
- `POST /api/servers/{id}/exec` — 执行命令（body: command），返回输出。
- `POST /api/servers/{id}/deploy/upload` — 支持 multipart 文件上传（或本地路径）。

## 依赖与前置条件

- spec-008（servers 存储、ssh 模块、paramiko）。
- AntD 组件（无需新增图表库）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- nvidia-smi 解析格式因驱动/环境而异，需容错。
- 大文件上传耗时，需超时/提示。
