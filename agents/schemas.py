from typing import List, Optional, Any
from pydantic import BaseModel, Field

class FileList(BaseModel):
    """The strict output format for the Parser Agent."""
    paths: List[str] = Field(
        ..., 
        description="A list of valid file paths found in the directory."
    )