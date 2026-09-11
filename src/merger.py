"""
Topic Boundary Merger, Digression Filter, and Deduplication Engine.
Combines cross-chunk segments, absorbs short conversational digressions and objections,
and guarantees chronological ordering.
"""

from typing import List
from difflib import SequenceMatcher
from src.models import TopicEntry


class TopicMerger:
    """
    Post-processes candidate topics to eliminate redundancy from chunk overlap,
    absorb brief attorney objections, and merge contiguous discussion threads.
    """

    def __init__(self, title_similarity_threshold: float = 0.70, max_objection_lines: int = 4):
        self.title_similarity_threshold = title_similarity_threshold
        self.max_objection_lines = max_objection_lines

    def merge(self, entries: List[TopicEntry]) -> List[TopicEntry]:
        """Runs the complete merging, deduplication, and boundary smoothing pipeline."""
        if not entries:
            return []

        # 1. Sort strictly by starting coordinate
        sorted_entries = sorted(
            entries,
            key=lambda e: (e.start_page, e.start_line, e.end_page, e.end_line)
        )

        # 2. Iterative merge of adjacent/overlapping topics
        merged: List[TopicEntry] = []
        for current in sorted_entries:
            if not merged:
                merged.append(current)
                continue

            prev = merged[-1]

            # Check for overlap or immediate adjacency
            overlap = self._has_overlap_or_adjacency(prev, current)
            similar = self._is_similar_topic(prev.topic, current.topic)

            if overlap and similar:
                # Merge into single encompassing topic
                prev.end_page = max(prev.end_page, current.end_page)
                if prev.end_page == current.end_page:
                    prev.end_line = max(prev.end_line, current.end_line)
                
                # Combine summaries if unique
                if current.summary and current.summary not in prev.summary:
                    prev.summary = f"{prev.summary} {current.summary}".strip()
                
                # Boost confidence upon consistent cross-chunk extraction
                prev.confidence = min(1.0, max(prev.confidence, current.confidence) + 0.05)
                continue

            # 3. Absorb micro-digressions (e.g. 1-3 line attorney objections)
            current_line_span = self._estimate_line_span(current)
            if current_line_span <= self.max_objection_lines and (
                "OBJECTION" in current.topic.upper() or "BREAK" in current.topic.upper()
            ):
                # Absorb into preceding parent topic
                prev.end_page = max(prev.end_page, current.end_page)
                prev.end_line = max(prev.end_line, current.end_line)
                continue

            merged.append(current)

        return merged

    def _has_overlap_or_adjacency(self, a: TopicEntry, b: TopicEntry) -> bool:
        """Determines if entry B starts within or immediately after entry A (within 3 lines)."""
        # If A starts after B ends, no overlap
        if a.start_page > b.end_page or (a.start_page == b.end_page and a.start_line > b.end_line):
            return False

        # If B starts before A ends, direct overlap
        if b.start_page < a.end_page or (b.start_page == a.end_page and b.start_line <= a.end_line + 3):
            return True

        # Adjacent across page boundaries (e.g., A ends at P07:L25, B starts at P08:L01)
        if b.start_page == a.end_page + 1 and a.end_line >= 23 and b.start_line <= 3:
            return True

        return False

    def _is_similar_topic(self, title1: str, title2: str) -> bool:
        """Calculates semantic label similarity ratio."""
        t1 = title1.strip().lower()
        t2 = title2.strip().lower()
        if t1 == t2 or t1 in t2 or t2 in t1:
            return True
        return SequenceMatcher(None, t1, t2).ratio() >= self.title_similarity_threshold

    def _estimate_line_span(self, entry: TopicEntry) -> int:
        """Estimates total line count spanned by topic entry."""
        if entry.start_page == entry.end_page:
            return max(1, entry.end_line - entry.start_line + 1)
        pages = max(0, entry.end_page - entry.start_page - 1)
        return (25 - entry.start_line + 1) + (pages * 25) + entry.end_line
