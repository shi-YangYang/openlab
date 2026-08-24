# Spec 目录

本目录存放项目的所有 Spec。每个 Spec 使用单独子目录，命名遵循 `spec-001-short-name` 格式。

## 命名规则

- 编号从 `001` 开始递增，短名使用小写英文并以 `-` 连接。
- 示例：`spec-001-project-init`、`spec-002-literature-mining`。

## 目录结构

每个 Spec 子目录至少包含：

```
specs/spec-XXX-short-name/
  spec.md         # 需求规格说明
  plan.md         # 实施计划
  acceptance.md   # 验收标准与验收记录
```

## 状态说明

Spec 的生命周期：`draft（起草）` → `confirmed（已确认）` → `implementing（实施中）` → `accepted（已验收）` → `reworking（返工中）`。

状态建议在 `spec.md` 头部记录。模板见 `_template/`。

## 模板

新建 Spec 时，复制 `_template/` 目录并按实际情况填写。
