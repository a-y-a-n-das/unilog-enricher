from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    product_name: str | None = None
    search_queries: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)


class SourceAnalysis(BaseModel):
    url: str
    relevance: str
    authority: str
    source_type: str
    should_ingest: bool
    notes: str


class SourceVerificationResult(BaseModel):
    sources: list[SourceAnalysis] = Field(default_factory=list)