"""Markdown export helpers for single-paper analyses and comparative reviews."""
from typing import Any, Dict, List

_LANGUAGE_LABEL = {"zh": "中文", "en": "English"}


def _bullets(items: List[str]) -> str:
    if not items:
        return "-"
    return "\n".join(f"- {item}" for item in items)


def analysis_to_markdown(
    analysis: Dict[str, Any], paper: Dict[str, Any], language: str
) -> str:
    """Render a single-paper structured analysis as Markdown (FR-8)."""
    summary = analysis.get("summary", {})
    experiments = analysis.get("experiments", {})
    lang_label = _LANGUAGE_LABEL.get(language, language)
    title = paper.get("title") or paper.get("arxiv_id") or ""

    lines = [
        f"# 论文分析：{title}",
        "",
        f"- arXiv: `{paper.get('arxiv_id', '')}`",
        f"- 语言: {lang_label}",
        "",
        "## 总结",
        "",
        f"### 研究问题",
        summary.get("research_problem") or "-",
        "",
        "### 方法",
        summary.get("method") or "-",
        "",
        "### 贡献",
        _bullets(summary.get("contributions", [])),
        "",
        "### 结论",
        summary.get("conclusion") or "-",
        "",
        "## 实验与结果",
        "",
        "### 数据集",
        _bullets(experiments.get("datasets", [])),
        "",
        "### 基线",
        _bullets(experiments.get("baselines", [])),
        "",
        "### 评测指标",
        _bullets(experiments.get("metrics", [])),
        "",
        "### 关键结果",
        experiments.get("key_results") or "-",
        "",
        "## 局限与展望",
        "",
        "### 局限性",
        analysis.get("limitations") or "-",
        "",
        "### 未来工作",
        analysis.get("future_work") or "-",
        "",
        "## 关键词",
        "",
        _bullets(analysis.get("keywords", [])),
        "",
        "## 标签",
        "",
        _bullets(analysis.get("tags", [])),
    ]
    return "\n".join(lines) + "\n"


def review_to_markdown(
    review: Dict[str, Any], papers: List[Dict[str, Any]], language: str
) -> str:
    """Render a comparative review as Markdown (FR-8)."""
    lang_label = _LANGUAGE_LABEL.get(language, language)
    titles = ", ".join(
        p.get("title") or p.get("arxiv_id") or "" for p in papers if p
    )

    lines = [
        "# 对比综述",
        "",
        f"- 论文: {titles}",
        f"- 语言: {lang_label}",
        "",
        "## 共同主题",
        "",
        _bullets(review.get("common_themes", [])),
        "",
        "## 差异",
        "",
        _bullets(review.get("differences", [])),
        "",
        "## 研究空白",
        "",
        _bullets(review.get("research_gaps", [])),
        "",
        "## 总结",
        "",
        review.get("summary") or "-",
    ]
    return "\n".join(lines) + "\n"


def innovations_to_markdown(
    innovations: List[Dict[str, Any]], papers: List[Dict[str, Any]], language: str
) -> str:
    """Render a list of innovation points as Markdown (FR-8)."""
    lang_label = _LANGUAGE_LABEL.get(language, language)
    titles = ", ".join(
        p.get("title") or p.get("arxiv_id") or "" for p in papers if p
    )

    lines = [
        "# 创新点设计",
        "",
        f"- 论文: {titles}",
        f"- 语言: {lang_label}",
        "",
    ]
    for idx, point in enumerate(innovations, start=1):
        lines += [
            f"## 创新点 {idx}",
            "",
            f"**标题**: {point.get('title') or '-'}",
            "",
            f"**描述**: {point.get('description') or '-'}",
            "",
            "**创新依据**:",
            _bullets(point.get("basis", [])),
            "",
            f"**预期贡献**: {point.get('expected_contribution') or '-'}",
            "",
        ]
    return "\n".join(lines) + "\n"


def experiments_to_markdown(
    experiments: List[Dict[str, Any]], source: str, language: str
) -> str:
    """Render a list of experiment plans as Markdown (FR-8)."""
    lang_label = _LANGUAGE_LABEL.get(language, language)

    lines = [
        "# 实验方案设计",
        "",
        f"- 来源: {source}",
        f"- 语言: {lang_label}",
        "",
    ]
    for idx, plan in enumerate(experiments, start=1):
        lines += [
            f"## 方案 {idx}",
            "",
            "### 假设",
            plan.get("hypothesis") or "-",
            "",
            "### 目标",
            plan.get("goal") or "-",
            "",
            "### 数据集",
            _bullets(plan.get("datasets", [])),
            "",
            "### 基线",
            _bullets(plan.get("baselines", [])),
            "",
            "### 评价指标",
            _bullets(plan.get("metrics", [])),
            "",
        ]
    return "\n".join(lines) + "\n"
