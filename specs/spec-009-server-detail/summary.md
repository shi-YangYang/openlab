# spec-009 汇总：服务器详情页与监控可视化

> 本文档汇总 spec-009 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-009-server-detail`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-server-detail.md`

## 背景与目标

在 spec-008 的基础上优化交互：新增服务器二级详情页，整合监控可视化、部署增强、环境配置等能力。

## 功能需求清单（FR-1 ~ FR-7，全部完成）

- FR-1：一级列表每服务器四个操作（编辑/详情/删除/测试）。
- FR-2：二级详情页 + 面包屑「服务器列表 / 服务器名」。
- FR-3：监控可视化（GPU 表格+利用率进度条、CPU 负载、内存/磁盘进度、进程）。
- FR-4：监控结构化返回（gpu/load/memory/disk/processes/raw），解析失败回退 raw。
- FR-5：部署本地路径手动输入 + 文件/文件夹选择器上传。
- FR-6：环境配置预设命令 + 自定义命令执行。
- FR-7：命令执行结果展示。

非功能：NFR-1 paramiko；NFR-2 凭据安全；NFR-3 监控解析容错。

## 后端接口

- `POST /api/servers/{id}/monitor` — 结构化监控（含 raw 回退）
- `POST /api/servers/{id}/exec` — 执行命令
- `POST /api/servers/{id}/deploy/upload` — multipart 文件上传 + 本地路径

## 验收结果

- 轮次 1：FAIL —— 发现路径穿越安全缺陷（`_safe_rel_path` 未处理绝对路径）。
- 轮次 2：PASS —— 返工修复（剥离绝对路径前缀 + resolve 校验），AC-1~9 全部通过。

`pytest` **142 passed**；前端 `npm run build` 通过。

## 使用方式

- 顶部「服务器」页 → 点某服务器「详情」→ 详情页：监控可视化、部署（git clone / 上传）、环境配置（预设+自定义命令）。
