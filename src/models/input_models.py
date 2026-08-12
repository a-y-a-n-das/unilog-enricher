from typing import Any
from pydantic import BaseModel, Field


class InputRecord(BaseModel):
    row_number: int
    data: dict[str, Any]