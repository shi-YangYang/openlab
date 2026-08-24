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
