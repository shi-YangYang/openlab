# 文档规范

约束项目文档编写行为。

## README

- README 必须遵循 [standard-readme](https://github.com/RichardLitt/standard-readme) 规范。
- 章节须按规范顺序排列，标题按规范命名（双语时标题翻译为对应语言）。
- 必填章节：标题（Title）、简短描述（Short Description）、目录（长于 100 行时）、安装（Install）、使用（Usage）、贡献（Contributing）、许可证（License，必须为最后一节）。
- 可选章节按需选用（Security、Background、API、Maintainers、Thanks 等），放置位置遵循规范。
- 双语项目：`README.md` 为英文，`README.zh.md` 为中文（命名遵循 BCP 47）。
- 不得包含失效链接；代码示例需与项目代码同等规范。
- 许可证需列 SPDX 标识或全称，并注明版权所有者（本项目为 MIT）。

## 其它

- 文档改动与代码改动一同评审；重要文档结论留痕（见 `.ai/decisions/`）。
- 新增/修改 README 前，先对照 standard-readme 规范核对章节与顺序。
