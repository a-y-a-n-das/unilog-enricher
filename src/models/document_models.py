from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    source: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)