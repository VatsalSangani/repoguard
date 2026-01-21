from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

class Task(BaseModel):
    type: Literal["markdown_validate", "python_validate", "secrets_scan"]
    target: str = Field(description="File path or Folder path to validate")

class ParserInput(BaseModel):
    paths_str: str = Field(description="Raw input string containing one or more paths")

class ParserOutput(BaseModel):
    tasks: List[Task]
    error: Optional[str] = None

class ProcessingInput(BaseModel):
    scan_result: ParserOutput

class PlannedToolCall(BaseModel):
    tool: str
    args: Dict[str, Any]
    reason: str

class ProcessingOutput(BaseModel):
    plan: List[PlannedToolCall]

class AggregatorInput(BaseModel):
    parser_summary: Dict[str, Any] = Field(default={})
    results: List[Any]

class FinalReport(BaseModel):
    summary: Dict[str, Any]
    critical_findings: List[str]
    next_steps: List[str]