"""
Silent Omission Detector & Full Coverage Auditor.
Verifies that 100% of substantive deposition lines are accounted for,
detecting unassigned gaps and distinguishing benign administrative breaks from lost dialogue.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from src.models import TopicEntry, TranscriptLine


class UncoveredSegment(BaseModel):
    start_page: int
    start_line: int
    end_page: int
    end_line: int
    line_count: int
    sample_text: str
    is_administrative: bool = False


class OmissionReport(BaseModel):
    total_lines: int
    covered_lines: int
    coverage_percentage: float
    uncovered_segments: List[UncoveredSegment] = Field(default_factory=list)
    has_critical_omissions: bool = False


class OmissionDetector:
    """Audits a TopicIndex against canonical transcript lines to ensure zero silent omissions."""

    def __init__(self, canonical_lines: List[TranscriptLine]):
        self.canonical_lines = canonical_lines
        self.line_count = len(canonical_lines)
        self.line_by_coord = {(l.page, l.line): l for l in canonical_lines}

    def audit(self, topics: List[TopicEntry]) -> OmissionReport:
        """Determines line-by-line coverage and surfaces any silently skipped testimony blocks."""
        covered_set = set()

        for t in topics:
            cur_p = t.start_page
            cur_l = t.start_line
            while (cur_p < t.end_page) or (cur_p == t.end_page and cur_l <= t.end_line):
                covered_set.add((cur_p, cur_l))
                cur_l += 1
                if cur_l > 25:
                    cur_p += 1
                    cur_l = 1

        uncovered_segments: List[UncoveredSegment] = []
        current_gap: List[TranscriptLine] = []

        for line in self.canonical_lines:
            coord = (line.page, line.line)
            if coord not in covered_set:
                current_gap.append(line)
            else:
                if current_gap:
                    uncovered_segments.append(self._create_segment(current_gap))
                    current_gap = []

        if current_gap:
            uncovered_segments.append(self._create_segment(current_gap))

        covered_count = len(covered_set.intersection(self.line_by_coord.keys()))
        coverage_pct = round((covered_count / max(1, self.line_count)) * 100, 2)

        # Flag critical omissions: any non-administrative gap spanning > 5 lines with text
        has_critical = any(
            (not s.is_administrative and s.line_count > 5) for s in uncovered_segments
        )

        return OmissionReport(
            total_lines=self.line_count,
            covered_lines=covered_count,
            coverage_percentage=coverage_pct,
            uncovered_segments=uncovered_segments,
            has_critical_omissions=has_critical
        )

    def _create_segment(self, gap_lines: List[TranscriptLine]) -> UncoveredSegment:
        combined_text = " ".join([l.text for l in gap_lines if l.text.strip()])
        is_admin = False

        # Detect court reporter recess / off-the-record notations
        upper = combined_text.upper()
        if (
            "RECESS" in upper
            or "OFF THE RECORD" in upper
            or "EXAMINATION CONTINUED" in upper
            or "WHEREUPON" in upper
            or not combined_text.strip()
        ):
            is_admin = True

        return UncoveredSegment(
            start_page=gap_lines[0].page,
            start_line=gap_lines[0].line,
            end_page=gap_lines[-1].page,
            end_line=gap_lines[-1].line,
            line_count=len(gap_lines),
            sample_text=combined_text[:120] if combined_text else "(Blank lines / formatting)",
            is_administrative=is_admin
        )
