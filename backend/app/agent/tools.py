"""Tool wrapping for the agent: expose existing backend capabilities as LangChain tools.

Every tool wraps an existing backend function (see spec-001~009) so the LLM can
orchestrate the full research pipeline. ``run_command`` and ``deploy_code`` are
flagged as dangerous (``metadata["dangerous"]``) and the manual loop pauses
before executing them so the user can approve or reject.
"""
import contextvars
import json
import shlex
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .. import analysis, database, downloader, experiment, innovation, monitor, servers, ssh
from ..arxiv import ArxivClient
from ..config import settings
from ..llm import decompose_topic
from ..search.aggregator import ALL_PLATFORMS, search as aggregate_search
from . import sandbox

# Tools that require explicit user approval before execution (FR-8/FR-9).
DANGEROUS_TOOLS = {
    "run_command",
    "deploy_code",
    "run_python_code",
    "run_shell_command",
    "create_server",
    "update_server",
    "delete_server",
    "deploy_upload",
    "run_experiment",
    "stop_experiment_run",
}

# The session id of the request currently executing tools, used by the dynamic
# tools (run_python_code / run_shell_command) to locate their per-session sandbox.
_CURRENT_SESSION_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "agent_current_session_id", default=None
)


def set_session_context(session_id: Optional[str]) -> None:
    """Record the session id for the duration of the current tool execution."""
    _CURRENT_SESSION_ID.set(session_id)


def _current_session() -> Optional[str]:
    return _CURRENT_SESSION_ID.get()


class SearchPapersArgs(BaseModel):
    query: str = Field(..., description="arXiv 检索关键词或检索式（英文）")
    max_results: int = Field(10, ge=1, le=100, description="返回结果数量")
    platforms: Optional[List[str]] = Field(
        None,
        description=f"搜索平台列表，可选值：{', '.join(ALL_PLATFORMS)}；不传则搜索全部",
    )


class SearchByTopicArgs(BaseModel):
    topic: str = Field(..., description="研究主题描述（可用中文或英文）")
    max_results: int = Field(10, ge=1, le=100, description="返回结果数量")
    platforms: Optional[List[str]] = Field(
        None,
        description=f"搜索平台列表，可选值：{', '.join(ALL_PLATFORMS)}；不传则搜索全部",
    )


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
    innovation_id: int = Field(..., description="作为方案依据的创新点记录 id")
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


class RunPythonCodeArgs(BaseModel):
    code: str = Field(..., description="要执行的 Python 代码")


class RunShellCommandArgs(BaseModel):
    command: str = Field(..., description="要执行的本地 shell 命令")


class RunExperimentArgs(BaseModel):
    experiment_id: int = Field(..., description="实验方案 id")
    server_id: str = Field(..., description="服务器 id")


class GetExperimentRunStatusArgs(BaseModel):
    run_id: int = Field(..., description="实验运行记录 id")


class CreateServerArgs(BaseModel):
    name: str = Field(..., description="服务器名称")
    host: str = Field(..., description="主机地址")
    username: str = Field(..., description="登录用户名")
    port: int = Field(22, ge=1, le=65535, description="SSH 端口")
    auth_type: str = Field("password", pattern="^(password|key)$", description="认证方式：password 或 key")
    password: Optional[str] = Field(None, description="密码（auth_type=password 时）")
    private_key: Optional[str] = Field(None, description="私钥内容（auth_type=key 时）")


class UpdateServerArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")
    name: Optional[str] = Field(None, description="服务器名称")
    host: Optional[str] = Field(None, description="主机地址")
    username: Optional[str] = Field(None, description="登录用户名")
    port: Optional[int] = Field(None, ge=1, le=65535, description="SSH 端口")
    auth_type: Optional[str] = Field(None, pattern="^(password|key)$", description="认证方式：password 或 key")
    password: Optional[str] = Field(None, description="密码")
    private_key: Optional[str] = Field(None, description="私钥内容")


class DeleteServerArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")


class DeployUploadArgs(BaseModel):
    server_id: str = Field(..., description="服务器 id")
    local_path: str = Field(..., description="本地文件或目录路径")
    remote_path: str = Field(..., description="远程目标路径")


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


async def search_papers(
    query: str, max_results: int = 10, platforms: Optional[List[str]] = None
) -> Dict[str, Any]:
    result = await aggregate_search(
        query,
        platforms=platforms,
        max_results=max_results,
        arxiv_client=_get_arxiv_client(),
    )
    return {
        "count": len(result["papers"]),
        "papers": _summarize(result["papers"]),
        "fallbacks": result["fallbacks"],
    }


async def search_by_topic(
    topic: str, max_results: int = 10, platforms: Optional[List[str]] = None
) -> Dict[str, Any]:
    query = await decompose_topic(topic)
    result = await aggregate_search(
        query,
        platforms=platforms,
        max_results=max_results,
        arxiv_client=_get_arxiv_client(),
    )
    return {
        "query": query,
        "count": len(result["papers"]),
        "papers": _summarize(result["papers"]),
        "fallbacks": result["fallbacks"],
    }


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
    innovation_id: int,
    count: int = 1,
    language: str = "zh",
) -> List[Dict[str, Any]]:
    plans = await experiment.generate_experiments(
        "innovation", innovation_id, [], language, count
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


async def run_experiment(experiment_id: int, server_id: str) -> Dict[str, Any]:
    """Create and launch an experiment run on the given server."""
    from ..experiment_runner import ExperimentRunDriver, build_default_steps

    plan = database.get_experiment(experiment_id)
    if plan is None:
        return {"error": f"Experiment not found: {experiment_id}"}
    if servers.get_server(server_id) is None:
        return {"error": f"Server not found: {server_id}"}

    workdir = f"~/openlab-experiments/{experiment_id}"
    steps = build_default_steps(workdir)

    # Ask the LLM to refine env-setup and training commands for this specific
    # plan; fall back to the defaults when generation fails.
    try:
        from ..llm_config import get_effective_config

        cfg = get_effective_config()
        if cfg.get("api_key"):
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                base_url=cfg["base_url"], api_key=cfg["api_key"],
                model=cfg["model"], temperature=0.2,
            )
            prompt = (
                "根据以下实验方案 JSON，生成在 Linux 服务器上执行的 setup_command"
                "（准备环境/安装依赖）与 launch_command（后台启动训练并打印 PID，"
                '形如 `cd {workdir} && nohup python train.py > train.log 2>&1 & echo $!`）。'
                f"工作目录统一使用 {workdir}。只返回 JSON 对象。\n方案：{json.dumps(plan.get('content'), ensure_ascii=False)}"
            )
            resp = await llm.ainvoke([("human", prompt)])
            raw = resp.content
            if isinstance(raw, list):
                text = "".join(
                    str(item.get("text", "")) if isinstance(item, dict) else str(item)
                    for item in raw
                )
            else:
                text = str(raw)
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(text[start : end + 1])
                if parsed.get("setup_command"):
                    steps["setup_env"] = parsed["setup_command"]
                if parsed.get("launch_command"):
                    steps["launch_training"] = parsed["launch_command"]
    except Exception:
        pass  # fall back to defaults silently; user can edit later

    run = database.create_experiment_run(
        experiment_id=experiment_id,
        server_id=server_id,
        mode="agent",
        remote_workdir=workdir,
        launch_command=steps.get("launch_training", ""),
    )
    run_id = run["id"]
    driver = ExperimentRunDriver.get_or_create(run_id)
    driver.start(steps)
    return {
        "run_id": run_id,
        "status": "started",
        "steps": steps,
        "message": (
            f"实验运行已启动（run_id={run_id}），可通过 get_experiment_run_status(run_id={run_id}) "
            f"查看进度；如需终止调用 stop_experiment_run(run_id={run_id})。"
        ),
    }


async def get_experiment_run_status(run_id: int) -> Dict[str, Any]:
    from ..experiment_runner import read_log_tail

    record = database.get_experiment_run(run_id)
    if record is None:
        return {"error": f"Experiment run not found: {run_id}"}
    return {
        **record,
        "log_tail": read_log_tail(run_id, 10),
    }


async def stop_experiment_run(run_id: int) -> Dict[str, Any]:
    from ..experiment_runner import ExperimentRunDriver

    driver = ExperimentRunDriver.get(run_id)
    if driver is None:
        # No live task; still try to kill a recorded PID by checking the run.
        record = database.get_experiment_run(run_id)
        if record is None:
            return {"error": f"Experiment run not found: {run_id}"}
        return {"message": "该运行没有活跃任务", "status": record.get("status")}
    await driver.stop_run()
    return {"message": "已停止", "run_id": run_id}


async def list_search_history() -> List[Dict[str, Any]]:
    return database.list_search_history()


async def list_innovations() -> List[Dict[str, Any]]:
    return database.list_innovation_history()


async def list_reviews() -> List[Dict[str, Any]]:
    return database.list_reviews()


async def list_experiments() -> List[Dict[str, Any]]:
    return database.list_experiments()


async def create_server(
    name: str,
    host: str,
    username: str,
    port: int = 22,
    auth_type: str = "password",
    password: Optional[str] = None,
    private_key: Optional[str] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "name": name,
        "host": host,
        "username": username,
        "port": port,
        "auth_type": auth_type,
    }
    if password:
        data["password"] = password
    if private_key:
        data["private_key"] = private_key
    return servers.redact(servers.add_server(data))


async def update_server(
    server_id: str,
    name: Optional[str] = None,
    host: Optional[str] = None,
    username: Optional[str] = None,
    port: Optional[int] = None,
    auth_type: Optional[str] = None,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if name is not None:
        data["name"] = name
    if host is not None:
        data["host"] = host
    if username is not None:
        data["username"] = username
    if port is not None:
        data["port"] = port
    if auth_type is not None:
        data["auth_type"] = auth_type
    if password:
        data["password"] = password
    if private_key:
        data["private_key"] = private_key
    updated = servers.update_server(server_id, data)
    if updated is None:
        return {"error": f"Server not found: {server_id}"}
    return servers.redact(updated)


async def delete_server(server_id: str) -> Dict[str, Any]:
    if not servers.delete_server(server_id):
        return {"error": f"Server not found: {server_id}"}
    return {"status": "deleted", "server_id": server_id}


async def deploy_upload(server_id: str, local_path: str, remote_path: str) -> Dict[str, Any]:
    server = servers.get_server(server_id)
    if server is None:
        return {"error": f"Server not found: {server_id}"}
    return ssh.upload(server, local_path, remote_path)


async def run_python_code(code: str) -> Dict[str, Any]:
    return sandbox.run_python(code, _current_session() or "default")


async def run_shell_command(command: str) -> Dict[str, Any]:
    return sandbox.run_shell(command, _current_session() or "default")


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
        "按关键词/检索式在多平台（arXiv/Semantic Scholar/百度学术/知网）检索论文，"
        "返回论文 arxiv_id、标题、摘要与发表日期；失败平台以 fallback 外链返回。",
        SearchPapersArgs,
    ),
    _tool(
        search_by_topic,
        "search_by_topic",
        "把一段研究主题描述拆解为检索式后在多平台检索论文。",
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
        "基于一条创新点记录一对一生成可执行的实验方案。",
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
    _tool(
        list_search_history,
        "list_search_history",
        "列出历史搜索记录（关键词、模式、时间），只读。",
        NoArgs,
    ),
    _tool(
        list_innovations,
        "list_innovations",
        "列出历史生成的创新点记录，只读。",
        NoArgs,
    ),
    _tool(
        list_reviews,
        "list_reviews",
        "列出历史生成的文献综述记录，只读。",
        NoArgs,
    ),
    _tool(
        list_experiments,
        "list_experiments",
        "列出历史生成的实验方案记录，只读。",
        NoArgs,
    ),
    _tool(
        create_server,
        "create_server",
        "新增一台 SSH 服务器（凭据脱敏返回）。危险操作，执行前需用户确认。",
        CreateServerArgs,
        dangerous=True,
    ),
    _tool(
        update_server,
        "update_server",
        "更新一台 SSH 服务器的配置（凭据脱敏返回）。危险操作，执行前需用户确认。",
        UpdateServerArgs,
        dangerous=True,
    ),
    _tool(
        delete_server,
        "delete_server",
        "删除一台 SSH 服务器。危险操作，执行前需用户确认。",
        DeleteServerArgs,
        dangerous=True,
    ),
    _tool(
        deploy_upload,
        "deploy_upload",
        "通过 SFTP 把本地文件/目录上传到远程服务器。危险操作，执行前需用户确认。",
        DeployUploadArgs,
        dangerous=True,
    ),
    _tool(
        run_python_code,
        "run_python_code",
        "在会话沙箱中执行一段 Python 代码并返回输出。危险操作，执行前需用户确认。",
        RunPythonCodeArgs,
        dangerous=True,
    ),
    _tool(
        run_shell_command,
        "run_shell_command",
        "在会话沙箱中执行一条本地 shell 命令并返回输出。危险操作，执行前需用户确认。",
        RunShellCommandArgs,
        dangerous=True,
    ),
    _tool(
        run_experiment,
        "run_experiment",
        "把指定实验方案自动部署到指定服务器并启动训练（环境准备/后台启动）。危险操作，执行前需用户确认。",
        RunExperimentArgs,
        dangerous=True,
    ),
    _tool(
        get_experiment_run_status,
        "get_experiment_run_status",
        "查询一次实验运行的状态、当前步骤与最近日志。",
        GetExperimentRunStatusArgs,
    ),
    _tool(
        stop_experiment_run,
        "stop_experiment_run",
        "终止一次正在运行的实验（终止远端进程并标记停止）。危险操作，执行前需用户确认。",
        GetExperimentRunStatusArgs,
        dangerous=True,
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
