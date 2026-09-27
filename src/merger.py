"""
Topic Boundary Merger, Digression Filter, and Deduplication Engine.
Combines cross-chunk segments, absorbs short conversational digressions and objections,
and guarantees chronological ordering.

This is Stage 6 of the Pinpo pipeline. Takes validated topics from the validator and
merges overlapping/duplicate topics that were extracted from overlapping chunks.

WHY THIS IS NEEDED:
  The chunker (BLOCK-10) creates overlapping chunks (e.g., pages 15-16 appear in both
  Chunk 2 and Chunk 3). If a topic spans these pages, BOTH chunks will extract it.
  The merger deduplicates these cross-chunk duplicates and merges adjacent pieces.
"""

from typing import List
from difflib import SequenceMatcher  # Used for fuzzy topic title matching
from src.models import TopicEntry


# =========================================================================
# [BLOCK-22: TopicMerger — Cross-Chunk Deduplication & Boundary Smoothing]
# WHAT: Post-processes validated topics to:
#   1. Merge duplicate/overlapping topics from overlapping chunks
#   2. Absorb micro-digressions (1-3 line objections) into parent topics
#   3. Ensure chronological ordering
# WHY: Without merging, the output would contain duplicate topics from
#      chunk overlap, and tiny "Attorney Objection" topics that fragment
#      the index. Lawyers want clean, consolidated topic chapters.
# HOW IT WORKS:
#   1. Sort all topics by start coordinate (chronological order)
#   2. For each topic, check if it overlaps/is adjacent to the previous one
#   3. If titles are similar AND they overlap → merge them
#   4. If >50% coordinate overlap → merge regardless of title similarity
#   5. If topic is ≤4 lines and titled "Objection"/"Break" → absorb into parent
# PARAMETERS:
#   title_similarity_threshold=0.70 — how similar titles must be to merge
#   max_objection_lines=4 — max line span for a topic to be treated as a digression
# =========================================================================
class TopicMerger:
    """
    Post-processes candidate topics to eliminate redundancy from chunk overlap,
    absorb brief attorney objections, and merge contiguous discussion threads.
    """

    def __init__(self, title_similarity_threshold: float = 0.70, max_objection_lines: int = 4):
        self.title_similarity_threshold = title_similarity_threshold  # Min SequenceMatcher ratio for title merge
        self.max_objection_lines = max_objection_lines  # Max line span for objection absorption

    # =========================================================================
    # [BLOCK-22A: merge() — Core Merge Algorithm]
    # WHAT: The main merge method. Processes sorted topics left-to-right,
    #       merging or absorbing each one as appropriate.
    # ALGORITHM:
    #   For each topic in sorted order:
    #     1. If no previous topic → just add it
    #     2. Check overlap/adjacency with previous topic
    #     3. Check title similarity with previous topic
    #     4. Merge if: (overlap AND similar) OR (>50% overlap regardless)
    #     5. Absorb if: ≤4 lines AND title contains "OBJECTION" or "BREAK"
    #     6. Otherwise → add as new separate topic
    # MERGE BEHAVIOR:
    #   - End coordinate = max of both topics' end coordinates
    #   - Summaries are concatenated if unique
    #   - Confidence gets a small boost (+0.05) for cross-chunk consistency
    # =========================================================================
    def merge(self, entries: List[TopicEntry]) -> List[TopicEntry]:
        """Runs the complete merging, deduplication, and boundary smoothing pipeline."""
        if not entries:
            return []

        # Step 1: Sort strictly by starting coordinate (chronological order)
        sorted_entries = sorted(
            entries,
            key=lambda e: (e.start_page, e.start_line, e.end_page, e.end_line)
        )

        # Step 2: Iterative merge — process topics left-to-right
        merged: List[TopicEntry] = []
        for current in sorted_entries:
            if not merged:
                merged.append(current)  # First topic — just add it
                continue

            prev = merged[-1]  # The last topic in the merged list

            # Check for overlap or immediate adjacency with previous topic
            overlap = self._has_overlap_or_adjacency(prev, current)
            # Check if topic titles are semantically similar
            similar = self._is_similar_topic(prev.topic, current.topic)

            # Compute coordinate overlap ratio (0.0 to 1.0)
            # >50% overlap means they're essentially the same topic region
            significant_overlap = overlap and self._compute_overlap_ratio(prev, current) > 0.50

            if (overlap and similar) or significant_overlap:
                # --- MERGE: Combine into single encompassing topic ---
                # Extend end coordinate to the further of the two
                new_end_page = max(prev.end_page, current.end_page)
                if new_end_page > prev.end_page:
                    prev.end_page = new_end_page
                    prev.end_line = current.end_line
                elif new_end_page == prev.end_page:
                    prev.end_line = max(prev.end_line, current.end_line)
                
                # Combine summaries if the new summary adds unique information
                if current.summary and current.summary not in prev.summary:
                    prev.summary = f"{prev.summary} {current.summary}".strip()
                
                # Small confidence boost for cross-chunk extraction consistency
                # If the same topic was extracted from two overlapping chunks,
                # that's stronger evidence it's a real topic
                prev.confidence = min(1.0, max(prev.confidence, current.confidence) + 0.05)
                continue

            # Step 3: Check if current topic is a micro-digression (objection/break)
            current_line_span = self._estimate_line_span(current)
            if current_line_span <= self.max_objection_lines and (
                "OBJECTION" in current.topic.upper() or "BREAK" in current.topic.upper()
            ):
                # --- ABSORB: Fold the digression into the parent topic ---
                # Extend the parent's end coordinate to cover the digression
                prev.end_page = max(prev.end_page, current.end_page)
                if prev.end_page == current.end_page:
                    prev.end_line = max(prev.end_line, current.end_line)
                else:
                    prev.end_line = current.end_line
                continue  # Don't add digression as separate topic

            # No merge or absorption — add as a new separate topic
            merged.append(current)

        return merged

    # =========================================================================
    # [BLOCK-22B: Overlap & Adjacency Detection]
    # WHAT: Determines if two topics overlap or are immediately adjacent.
    # WHY: Adjacent topics with similar titles should be merged (they're likely
    #      the same discussion split across a chunk boundary).
    # ADJACENCY DEFINITION: "immediately after" means within 3 lines,
    #      or across a page boundary (e.g., P07:L25 → P08:L01).
    # =========================================================================
    def _has_overlap_or_adjacency(self, a: TopicEntry, b: TopicEntry) -> bool:
        """Determines if entry B starts within or immediately after entry A (within 3 lines)."""
        # If A starts after B ends, definitely no overlap
        if a.start_page > b.end_page or (a.start_page == b.end_page and a.start_line > b.end_line):
            return False

        # If B starts before A ends → direct overlap
        if b.start_page < a.end_page or (b.start_page == a.end_page and b.start_line <= a.end_line + 3):
            return True

        # Adjacent across page boundaries (e.g., A ends at P07:L25, B starts at P08:L01)
        if b.start_page == a.end_page + 1 and a.end_line >= 23 and b.start_line <= 3:
            return True

        return False

    # =========================================================================
    # [BLOCK-22C: Topic Title Similarity]
    # WHAT: Checks if two topic titles are semantically similar enough to merge.
    # HOW: Three checks in order of decreasing strictness:
    #   1. Exact match (lowercase)
    #   2. Substring containment (one title contains the other)
    #   3. SequenceMatcher ratio >= 0.70 (fuzzy match)
    # EXAMPLE:
    #   "Witness Background and Retainer" vs "Witness Background & Role" → ratio ≈ 0.75 → SIMILAR
    #   "Educational Background" vs "Loan Practices" → ratio ≈ 0.20 → NOT SIMILAR
    # =========================================================================
    def _is_similar_topic(self, title1: str, title2: str) -> bool:
        """Calculates semantic label similarity ratio."""
        t1 = title1.strip().lower()
        t2 = title2.strip().lower()
        # Exact match or substring containment
        if t1 == t2 or t1 in t2 or t2 in t1:
            return True
        # Fuzzy match using SequenceMatcher
        return SequenceMatcher(None, t1, t2).ratio() >= self.title_similarity_threshold

    # =========================================================================
    # [BLOCK-22D: Overlap Ratio Computation]
    # WHAT: Computes what fraction of the smaller topic's lines overlap with
    #       the larger topic. Returns 0.0 to 1.0.
    # WHY: If >50% of a topic's lines overlap with another, they should be
    #       merged even if titles don't match (prevents coordinate fragmentation).
    # HOW: Converts (page, line) coordinates to global line offsets, then
    #      computes intersection / smaller_span.
    # =========================================================================
    def _compute_overlap_ratio(self, a: TopicEntry, b: TopicEntry) -> float:
        """Computes the fraction of the smaller topic's lines that overlap with the larger topic."""
        # Convert to global line offsets: page_offset * 25 + line_number
        a_start = (a.start_page - 1) * 25 + a.start_line
        a_end = (a.end_page - 1) * 25 + a.end_line
        b_start = (b.start_page - 1) * 25 + b.start_line
        b_end = (b.end_page - 1) * 25 + b.end_line

        # Compute overlap range
        overlap_start = max(a_start, b_start)
        overlap_end = min(a_end, b_end)
        overlap_lines = max(0, overlap_end - overlap_start + 1)

        # Normalize by smaller topic's span
        smaller_span = min(a_end - a_start + 1, b_end - b_start + 1)
        if smaller_span <= 0:
            return 0.0
        return overlap_lines / smaller_span

    # =========================================================================
    # [BLOCK-22E: Line Span Estimation]
    # WHAT: Estimates how many transcript lines a topic entry spans.
    # WHY: Used to identify micro-digressions (≤4 lines) for absorption.
    # HOW: Simple arithmetic:
    #   Same page: end_line - start_line + 1
    #   Multiple pages: remaining_on_first + (middle_pages * 25) + lines_on_last
    # =========================================================================
    def _estimate_line_span(self, entry: TopicEntry) -> int:
        """Estimates total line count spanned by topic entry."""
        if entry.start_page == entry.end_page:
            return max(1, entry.end_line - entry.start_line + 1)
        # Multi-page span: lines on first page + full middle pages + lines on last page
        pages = max(0, entry.end_page - entry.start_page - 1)
        return (25 - entry.start_line + 1) + (pages * 25) + entry.end_line
