"""Pydantic request/response schemas."""
from typing import List, Optional

from pydantic import BaseModel, Field


class Paper(BaseModel):
    arxiv_id: str
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    abstract: str = ""
    categories: List[str] = Field(default_factory=list)
    published: str = ""
    pdf_url: str = ""


class PaperRecord(Paper):
    id: Optional[int] = None
    local_pdf_path: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = 0
    created_at: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=10, ge=1, le=100)
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class TopicSearchRequest(BaseModel):
    topic: str
    max_results: int = Field(default=10, ge=1, le=100)
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class TopicSearchResponse(BaseModel):
    query: str
    papers: List[Paper]


class SearchHistoryItem(BaseModel):
    id: int
    query: str
    mode: str
    paper_count: int
    created_at: Optional[str] = None


class SearchHistoryDetail(BaseModel):
    id: int
    query: str
    mode: str
    papers: List[Paper]
    created_at: Optional[str] = None


class DownloadRequest(BaseModel):
    papers: List[Paper]


class DownloadResponse(BaseModel):
    accepted: List[str]
    skipped: List[str]


class LLMPreset(BaseModel):
    name: str
    base_url: str
    default_model: str


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str


class LLMConfigUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LLMTestRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LLMTestResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: Optional[int] = None


class AnalysisSummary(BaseModel):
    research_problem: str = ""
    method: str = ""
    contributions: List[str] = Field(default_factory=list)
    conclusion: str = ""


class AnalysisExperiments(BaseModel):
    datasets: List[str] = Field(default_factory=list)
    baselines: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    key_results: str = ""


class PaperAnalysis(BaseModel):
    summary: AnalysisSummary
    experiments: AnalysisExperiments
    limitations: str = ""
    future_work: str = ""
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    common_themes: List[str] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)
    research_gaps: List[str] = Field(default_factory=list)
    summary: str = ""


class AnalyzeRequest(BaseModel):
    language: str = Field(default="zh", pattern="^(zh|en)$")


class AnalyzeBatchRequest(BaseModel):
    arxiv_ids: List[str] = Field(default_factory=list)
    language: str = Field(default="zh", pattern="^(zh|en)$")


class ReviewRequest(BaseModel):
    arxiv_ids: List[str] = Field(default_factory=list)
    language: str = Field(default="zh", pattern="^(zh|en)$")


class InnovationPoint(BaseModel):
    title: str = ""
    description: str = ""
    basis: List[str] = Field(default_factory=list)
    expected_contribution: str = ""


class InnovationRecord(BaseModel):
    id: Optional[int] = None
    arxiv_ids: List[str] = Field(default_factory=list)
    content: Optional[List[InnovationPoint]] = None
    language: str = "zh"
    status: str = "pending"
    error: Optional[str] = None
    progress: Optional[int] = 0
    created_at: Optional[str] = None


class InnovationHistoryItem(BaseModel):
    id: int
    arxiv_ids: List[str] = Field(default_factory=list)
    paper_count: int = 0
    innovation_count: int = 0
    language: str = "zh"
    status: str = "pending"
    created_at: Optional[str] = None


class InnovationRequest(BaseModel):
    arxiv_ids: List[str] = Field(default_factory=list)
    count: int = Field(default=3)
    language: str = Field(default="zh", pattern="^(zh|en)$")


class AnalyzeResponse(BaseModel):
    arxiv_id: str
    status: str


class AnalyzeBatchResponse(BaseModel):
    arxiv_ids: List[str]
    status: str


class AnalysisRecord(BaseModel):
    id: Optional[int] = None
    arxiv_id: str
    content: Optional[PaperAnalysis] = None
    language: str = "zh"
    status: str = "pending"
    error: Optional[str] = None
    progress: Optional[int] = 0
    message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReviewRecord(BaseModel):
    id: Optional[int] = None
    arxiv_ids: List[str] = Field(default_factory=list)
    content: Optional[ReviewResult] = None
    language: str = "zh"
    status: str = "pending"
    error: Optional[str] = None
    progress: Optional[int] = 0
    created_at: Optional[str] = None


class ExperimentPlan(BaseModel):
    hypothesis: str = ""
    goal: str = ""
    datasets: List[str] = Field(default_factory=list)
    baselines: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)


class ExperimentRecord(BaseModel):
    id: Optional[int] = None
    source_type: str = "papers"
    innovation_id: Optional[int] = None
    arxiv_ids: List[str] = Field(default_factory=list)
    content: Optional[List[ExperimentPlan]] = None
    language: str = "zh"
    status: str = "pending"
    error: Optional[str] = None
    progress: Optional[int] = 0
    created_at: Optional[str] = None


class ExperimentRequest(BaseModel):
    source_type: str = "papers"
    innovation_id: Optional[int] = None
    arxiv_ids: List[str] = Field(default_factory=list)
    count: int = Field(default=1)
    language: str = Field(default="zh", pattern="^(zh|en)$")


class ServerInput(BaseModel):
    name: str
    host: str
    username: str
    port: int = Field(default=22, ge=1, le=65535)
    auth_type: str = Field(default="password", pattern="^(password|key)$")
    password: Optional[str] = None
    private_key: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    username: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    auth_type: Optional[str] = Field(default=None, pattern="^(password|key)$")
    password: Optional[str] = None
    private_key: Optional[str] = None


class ServerOutput(BaseModel):
    id: str
    name: str
    host: str
    username: str
    port: int
    auth_type: str
    has_password: bool
    has_key: bool


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str
    latency_ms: Optional[int] = None


class CloneRequest(BaseModel):
    repo_url: str
    target_dir: str


class CloneResponse(BaseModel):
    output: str


class UploadRequest(BaseModel):
    local_path: str
    remote_path: str


class UploadResponse(BaseModel):
    message: str
    files: int
