"""
Silent Omission Detector & Full Coverage Auditor.
Verifies that 100% of substantive deposition lines are accounted for,
detecting unassigned gaps and distinguishing benign administrative breaks from lost dialogue.

This is Stage 7 (final stage) of the Pinpo pipeline. Takes the merged topic list
and the canonical transcript lines, and audits whether every line is covered by
at least one topic.

WHY THIS MATTERS:
  If a topic index silently skips 20 lines of testimony, a lawyer could miss
  critical testimony. The omission detector flags ANY gap > 5 substantive lines
  as a "critical omission" that needs investigation.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from src.models import TopicEntry, TranscriptLine


# =========================================================================
# [BLOCK-23: Omission Report Models — UncoveredSegment & OmissionReport]
# WHAT: Two Pydantic models for the omission audit results:
#   UncoveredSegment: Represents a contiguous gap of lines not covered by any topic
#   OmissionReport: The complete audit results with coverage statistics
# WHY: Structured output makes it easy to:
#   1. Display coverage percentage in the pipeline summary
#   2. Flag critical omissions for investigation
#   3. Distinguish benign gaps (recess, off-record) from lost testimony
# =========================================================================

class UncoveredSegment(BaseModel):
    """Represents a contiguous block of transcript lines not covered by any topic."""
    start_page: int  # Starting page of the gap
    start_line: int  # Starting line of the gap
    end_page: int  # Ending page of the gap
    end_line: int  # Ending line of the gap
    line_count: int  # Number of lines in this gap
    sample_text: str  # First 120 chars of text in the gap (for human review)
    is_administrative: bool = False  # True if gap is benign (recess, off-record, etc.)


class OmissionReport(BaseModel):
    """Complete audit results showing coverage statistics and any gaps."""
    total_lines: int  # Total canonical lines in the transcript
    covered_lines: int  # Lines covered by at least one topic
    coverage_percentage: float  # covered_lines / total_lines * 100
    uncovered_segments: List[UncoveredSegment] = Field(default_factory=list)  # List of gaps
    has_critical_omissions: bool = False  # True if any non-administrative gap > 5 lines


# =========================================================================
# [BLOCK-24: OmissionDetector — Line-by-Line Coverage Audit Engine]
# WHAT: Audits a topic index against the canonical transcript to ensure
#       every substantive line is covered by at least one topic.
# WHY: The LLM might miss sections of testimony, or the merger might
#       accidentally create gaps. The omission detector catches these.
# HOW IT WORKS:
#   1. Build a set of all (page, line) coordinates covered by topics
#      (by iterating through each topic's start→end coordinate range)
#   2. Walk through ALL canonical lines and identify which ones are NOT in the covered set
#   3. Group consecutive uncovered lines into UncoveredSegment objects
#   4. Classify each gap as administrative (recess/off-record) or critical (lost testimony)
#   5. Report coverage percentage and flag any critical omissions
# CLASSIFICATION:
#   Administrative (benign): Contains "RECESS", "OFF THE RECORD", "WHEREUPON", or is blank
#   Critical: Non-administrative gap spanning > 5 lines with actual text
# =========================================================================
class OmissionDetector:
    """Audits a TopicIndex against canonical transcript lines to ensure zero silent omissions."""

    def __init__(self, canonical_lines: List[TranscriptLine]):
        self.canonical_lines = canonical_lines  # The complete canonical transcript from the parser
        self.line_count = len(canonical_lines)  # Total line count
        # Build a coordinate lookup for quick membership checks
        self.line_by_coord = {(l.page, l.line): l for l in canonical_lines}

    def audit(self, topics: List[TopicEntry]) -> OmissionReport:
        """Determines line-by-line coverage and surfaces any silently skipped testimony blocks."""

        # Step 1: Build the set of ALL (page, line) coordinates covered by topics
        covered_set = set()
        for t in topics:
            # Walk from start_page:start_line to end_page:end_line, adding each coordinate
            cur_p = t.start_page
            cur_l = t.start_line
            while (cur_p < t.end_page) or (cur_p == t.end_page and cur_l <= t.end_line):
                covered_set.add((cur_p, cur_l))
                cur_l += 1
                if cur_l > 25:  # Court reporter pages have lines 1..25
                    cur_p += 1
                    cur_l = 1

        # Step 2: Walk through ALL canonical lines and find uncovered ones
        uncovered_segments: List[UncoveredSegment] = []
        current_gap: List[TranscriptLine] = []  # Accumulates consecutive uncovered lines

        for line in self.canonical_lines:
            coord = (line.page, line.line)
            if coord not in covered_set:
                # This line is NOT covered by any topic → add to current gap
                current_gap.append(line)
            else:
                # This line IS covered → close any open gap
                if current_gap:
                    uncovered_segments.append(self._create_segment(current_gap))
                    current_gap = []

        # Close any trailing gap at the end of the transcript
        if current_gap:
            uncovered_segments.append(self._create_segment(current_gap))

        # Step 3: Calculate coverage statistics
        covered_count = len(covered_set.intersection(self.line_by_coord.keys()))
        coverage_pct = round((covered_count / max(1, self.line_count)) * 100, 2)

        # Step 4: Flag critical omissions
        # Critical = non-administrative gap spanning > 5 lines with actual text
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

    # =========================================================================
    # [BLOCK-24A: Gap Classification — Administrative vs Critical]
    # WHAT: Takes a list of consecutive uncovered lines and creates an
    #       UncoveredSegment, classifying it as administrative or critical.
    # HOW: Checks the combined text for administrative keywords:
    #   - "RECESS" → court took a break
    #   - "OFF THE RECORD" → discussion not recorded
    #   - "EXAMINATION CONTINUED" → procedural resumption
    #   - "WHEREUPON" → court reporter notation
    #   - Empty text → blank lines / formatting
    # WHY: Lawyers don't care about recess gaps — they only care about
    #      lost testimony that might contain critical evidence.
    # =========================================================================
    def _create_segment(self, gap_lines: List[TranscriptLine]) -> UncoveredSegment:
        """Creates an UncoveredSegment from a list of consecutive uncovered lines."""
        # Combine text from all lines in the gap for classification
        combined_text = " ".join([l.text for l in gap_lines if l.text.strip()])
        is_admin = False

        # Classify: check for administrative/procedural keywords
        upper = combined_text.upper()
        if (
            "RECESS" in upper
            or "OFF THE RECORD" in upper
            or "EXAMINATION CONTINUED" in upper
            or "WHEREUPON" in upper
            or not combined_text.strip()  # Blank lines = formatting, not lost testimony
        ):
            is_admin = True  # This gap is benign (administrative)

        return UncoveredSegment(
            start_page=gap_lines[0].page,
            start_line=gap_lines[0].line,
            end_page=gap_lines[-1].page,
            end_line=gap_lines[-1].line,
            line_count=len(gap_lines),
            sample_text=combined_text[:120] if combined_text else "(Blank lines / formatting)",
            is_administrative=is_admin
        )
