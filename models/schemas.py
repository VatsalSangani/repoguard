from typing import List
from pydantic import BaseModel, Field


class FileList(BaseModel):
    """Strict output format for the Parser Agent."""

    paths: List[str] = Field(
        ...,
        description="A list of valid file paths found in the directory.",
    )
