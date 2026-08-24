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
