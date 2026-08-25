"""Tool wrapping for the agent: expose existing backend capabilities as LangChain tools.

Every tool wraps an existing backend function (see spec-001~009) so the LLM can
orchestrate the full research pipeline. ``run_command`` and ``deploy_code`` are
flagged as dangerous (``metadata["dangerous"]``) and the manual loop pauses
before executing them so the user can approve or reject.
"""
import shlex
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .. import analysis, database, downloader, experiment, innovation, monitor, servers, ssh
from ..arxiv import ArxivClient
from ..config import settings
from ..llm import decompose_topic

# Tools that require explicit user approval before execution (FR-8/FR-9).
DANGEROUS_TOOLS = {"run_command", "deploy_code"}


class SearchPapersArgs(BaseModel):
    query: str = Field(..., description="arXiv 检索关键词或检索式（英文）")
    max_results: int = Field(10, ge=1, le=100, description="返回结果数量")


class SearchByTopicArgs(BaseModel):
    topic: str = Field(..., description="研究主题描述（可用中文或英文）")
    max_results: int = Field(10, ge=1, le=100, description="返回结果数量")


class DownloadPapersArgs(BaseModel):
    arxiv_ids: List[str] = Field(..., description="要下载的论文 arxiv_id 列表")


class AnalyzePaperArgs(BaseModel):
    arxiv_id: str = Field(..., description="论文 arxiv_id（需已下载）")
    language: str = Field("zh", description="输出语言：zh 或 en")


class ReviewPapersArgs(BaseModel):
    arxiv_ids: List[str] = Field(..., description="进行综述对比的论文 arxiv_id 列表（至少 2 篇）")
    language: str = Field("zh", description="输出语言：zh 或 en")


class InnovationArgs(BaseModel):
    arxiv_ids: List[str] = Field(..., description="用于生成创新点的论文 arxiv_id 列表")
    count: int = Field(3, ge=1, le=10, description="创新点数量")
    language: str = Field("zh", description="输出语言：zh 或 en")


class DesignExperimentArgs(BaseModel):
    source_type: str = Field(..., description="实验设计依据来源：innovation 或 papers")
    innovation_id: Optional[int] = Field(None, description="source_type=innovation 时的创新点 id")
    arxiv_ids: Optional[List[str]] = Field(None, description="source_type=papers 时的论文 arxiv_id 列表")
    count: int = Field(1, ge=1, le=3, description="实验方案数量")
    language: str = Field("zh", description="输出语言：zh 或 en")


class ServerIdArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")


class DeployCodeArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")
    repo_url: str = Field(..., description="Git 仓库地址")
    target_dir: str = Field(..., description="远程目标目录")


class RunCommandArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")
    command: str = Field(..., description="要在远程服务器上执行的 shell 命令")


class NoArgs(BaseModel):
    pass


_client: Optional[ArxivClient] = None


def _get_arxiv_client() -> ArxivClient:
    global _client
    if _client is None:
        _client = ArxivClient(
            interval=settings.arxiv_request_interval,
            max_retries=settings.arxiv_max_retries,
        )
    return _client


def _summarize(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "arxiv_id": p.get("arxiv_id", ""),
            "title": p.get("title", ""),
            "abstract": p.get("abstract", ""),
            "published": p.get("published", ""),
        }
        for p in papers
    ]


async def search_papers(query: str, max_results: int = 10) -> Dict[str, Any]:
    papers = await _get_arxiv_client().search(query, max_results=max_results)
    return {"count": len(papers), "papers": _summarize(papers)}


async def search_by_topic(topic: str, max_results: int = 10) -> Dict[str, Any]:
    query = await decompose_topic(topic)
    papers = await _get_arxiv_client().search(query, max_results=max_results)
    return {"query": query, "count": len(papers), "papers": _summarize(papers)}


async def download_papers(arxiv_ids: List[str]) -> Dict[str, Any]:
    papers: List[Dict[str, Any]] = []
    for arxiv_id in arxiv_ids:
        paper = database.get_paper(arxiv_id)
        if paper is None:
            paper = {"arxiv_id": arxiv_id, "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}"}
            database.upsert_paper(paper)
        elif not paper.get("pdf_url"):
            paper["pdf_url"] = f"https://arxiv.org/pdf/{arxiv_id}"
            database.upsert_paper(paper)
        papers.append(paper)

    await downloader.run_download_job(papers)

    statuses: Dict[str, str] = {}
    for arxiv_id in arxiv_ids:
        record = database.get_paper(arxiv_id)
        statuses[arxiv_id] = record.get("status") if record else "unknown"
    return {"statuses": statuses}


async def list_downloaded_papers() -> Dict[str, Any]:
    papers = database.list_papers()
    downloaded = [p for p in papers if p.get("status") == "downloaded"]
    return {
        "count": len(downloaded),
        "papers": [
            {"arxiv_id": p.get("arxiv_id", ""), "title": p.get("title", "")}
            for p in downloaded
        ],
    }


async def analyze_paper(arxiv_id: str, language: str = "zh") -> Dict[str, Any]:
    if not downloader.is_downloaded(arxiv_id):
        return {"arxiv_id": arxiv_id, "error": f"论文尚未下载，请先下载: {arxiv_id}"}
    await analysis.run_analysis_job([arxiv_id], language)
    record = database.get_analysis(arxiv_id)
    if record and record.get("content") is not None:
        return {"arxiv_id": arxiv_id, "analysis": record["content"]}
    return {
        "arxiv_id": arxiv_id,
        "error": (record or {}).get("error") or "分析失败",
    }


async def review_papers(arxiv_ids: List[str], language: str = "zh") -> Dict[str, Any]:
    result = await analysis.generate_review(arxiv_ids, language)
    return result.model_dump()


async def generate_innovation_points(
    arxiv_ids: List[str], count: int = 3, language: str = "zh"
) -> List[Dict[str, Any]]:
    points = await innovation.generate_innovations(arxiv_ids, language, count)
    return [p.model_dump() for p in points]


async def design_experiment(
    source_type: str,
    innovation_id: Optional[int] = None,
    arxiv_ids: Optional[List[str]] = None,
    count: int = 1,
    language: str = "zh",
) -> List[Dict[str, Any]]:
    plans = await experiment.generate_experiments(
        source_type, innovation_id, arxiv_ids or [], language, count
    )
    return [p.model_dump() for p in plans]


async def list_servers() -> List[Dict[str, Any]]:
    return [servers.redact(s) for s in servers.list_servers()]


async def test_server_connection(server_id: str) -> Dict[str, Any]:
    server = servers.get_server(server_id)
    if server is None:
        return {"ok": False, "message": f"Server not found: {server_id}"}
    return ssh.test_connection(server)


async def deploy_code(server_id: str, repo_url: str, target_dir: str) -> Dict[str, Any]:
    server = servers.get_server(server_id)
    if server is None:
        return {"error": f"Server not found: {server_id}"}
    command = f"git clone {shlex.quote(repo_url)} {shlex.quote(target_dir)}"
    return {"output": ssh.exec_command(server, command)}


async def run_command(server_id: str, command: str) -> Dict[str, Any]:
    server = servers.get_server(server_id)
    if server is None:
        return {"error": f"Server not found: {server_id}"}
    return {"output": ssh.exec_command(server, command)}


async def monitor_server(server_id: str) -> Dict[str, Any]:
    server = servers.get_server(server_id)
    if server is None:
        return {"error": f"Server not found: {server_id}"}
    return monitor.collect(server)


def _tool(
    coroutine: Any,
    name: str,
    description: str,
    args_schema: type,
    dangerous: bool = False,
) -> StructuredTool:
    metadata = {"dangerous": dangerous}
    return StructuredTool.from_function(
        coroutine=coroutine,
        name=name,
        description=description,
        args_schema=args_schema,
        metadata=metadata,
    )


TOOLS: List[StructuredTool] = [
    _tool(
        search_papers,
        "search_papers",
        "按关键词/检索式在 arXiv 检索论文，返回论文 arxiv_id、标题、摘要与发表日期。",
        SearchPapersArgs,
    ),
    _tool(
        search_by_topic,
        "search_by_topic",
        "把一段研究主题描述拆解为检索式后在 arXiv 检索论文。",
        SearchByTopicArgs,
    ),
    _tool(
        download_papers,
        "download_papers",
        "下载一组论文的 PDF 到本地论文库，供后续分析使用。",
        DownloadPapersArgs,
    ),
    _tool(
        list_downloaded_papers,
        "list_downloaded_papers",
        "列出本地已下载的论文。",
        NoArgs,
    ),
    _tool(
        analyze_paper,
        "analyze_paper",
        "分析一篇已下载的论文，输出结构化分析（研究问题、方法、贡献、实验、局限等）。",
        AnalyzePaperArgs,
    ),
    _tool(
        review_papers,
        "review_papers",
        "对多篇论文做对比综述，归纳共同主题、差异与研究空白。",
        ReviewPapersArgs,
    ),
    _tool(
        generate_innovation_points,
        "generate_innovation_points",
        "基于一篇或多篇论文的分析生成科研创新点。",
        InnovationArgs,
    ),
    _tool(
        design_experiment,
        "design_experiment",
        "基于创新点或论文分析设计可执行的实验方案。",
        DesignExperimentArgs,
    ),
    _tool(
        list_servers,
        "list_servers",
        "列出已配置的 SSH 服务器（不含凭据）。",
        NoArgs,
    ),
    _tool(
        test_server_connection,
        "test_server_connection",
        "测试某台服务器的 SSH 连接是否可用。",
        ServerIdArgs,
    ),
    _tool(
        deploy_code,
        "deploy_code",
        "通过 git clone 将代码仓库部署到远程服务器。危险操作，执行前需用户确认。",
        DeployCodeArgs,
        dangerous=True,
    ),
    _tool(
        run_command,
        "run_command",
        "在远程服务器上执行一条 shell 命令并返回输出。危险操作，执行前需用户确认。",
        RunCommandArgs,
        dangerous=True,
    ),
    _tool(
        monitor_server,
        "monitor_server",
        "采集远程服务器的 GPU/内存/磁盘/负载等运行状态。",
        ServerIdArgs,
    ),
]

TOOLS_BY_NAME: Dict[str, StructuredTool] = {tool.name: tool for tool in TOOLS}


def get_tools() -> List[StructuredTool]:
    return list(TOOLS)


def is_dangerous(name: str) -> bool:
    return name in DANGEROUS_TOOLS


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")
    return await tool.ainvoke(args)
