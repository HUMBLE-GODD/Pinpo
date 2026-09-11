"""
Data models for Pinpo (AI-Powered Deposition Topic Index).
Defines schemas for canonical transcript lines, topic entries, and complete indices.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TranscriptLine(BaseModel):
    """Represents an atomic, canonically addressed line in a deposition transcript."""
    global_line_id: int = Field(..., description="Unique sequential line index across the entire transcript (1..N)")
    page: int = Field(..., description="Official printed transcript page number (e.g., 7..88)")
    line: int = Field(..., description="Line number on the page (typically 1..25)")
    speaker: str = Field(default="", description="Identified speaker (e.g., 'Q', 'A', 'MR. PURCELL', 'THE WITNESS')")
    text: str = Field(..., description="Cleaned spoken text for the line, stripped of line numbers & timestamps")
    timestamp: Optional[str] = Field(default=None, description="Recorded video timestamp (e.g., '01:17')")
    raw_text: str = Field(default="", description="Original raw line string as extracted from source")

    @property
    def coordinate(self) -> str:
        """Formatted coordinate string, e.g., 'Page 12, Line 4'."""
        return f"Page {self.page}, Line {self.line}"


class TopicEntry(BaseModel):
    """Represents a verified, chronologically ordered topic segment in the transcript."""
    topic: str = Field(..., description="Concise, attorney-friendly topic label (e.g., 'Employment History')")
    start_page: int = Field(..., description="Starting printed page number")
    start_line: int = Field(..., description="Starting line number (1..25)")
    end_page: int = Field(..., description="Ending printed page number")
    end_line: int = Field(..., description="Ending line number (1..25)")
    start_global_id: Optional[int] = Field(default=None, description="Starting global sequential line ID")
    end_global_id: Optional[int] = Field(default=None, description="Ending global sequential line ID")
    summary: str = Field(default="", description="Brief factual summary of testimony within this segment")
    supporting_quote: str = Field(default="", description="Verbatim quote from the transcript anchoring this topic")
    confidence: float = Field(default=1.0, description="Confidence/validation score (0.0 to 1.0)")
    verified: bool = Field(default=False, description="Whether start and end lines were deterministically verified against raw transcript")

    @property
    def start_coordinate(self) -> str:
        return f"Page {self.start_page}, Line {self.start_line}"

    @property
    def end_coordinate(self) -> str:
        return f"Page {self.end_page}, Line {self.end_line}"


class TopicIndex(BaseModel):
    """Complete structured Topic Index representing the entire deposition."""
    title: str = Field(default="Deposition Topic Index", description="Title of the deposition index")
    witness: str = Field(default="Persis Yu", description="Name of the deponent / witness")
    date: Optional[str] = Field(default=None, description="Date of the deposition")
    case_name: Optional[str] = Field(default=None, description="Case / matter name")
    total_pages: int = Field(..., description="Total pages processed")
    total_lines: int = Field(..., description="Total substantive lines processed")
    topics: List[TopicEntry] = Field(default_factory=list, description="List of chronologically ordered topic entries")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Pipeline configuration, timestamps, model parameters")
