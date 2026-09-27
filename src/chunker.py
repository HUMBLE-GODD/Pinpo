"""
Transcript Chunker with coordinate-aware windowing and overlap.
Divides canonical transcript lines into contextual segments for LLM processing,
preserving page and line coordinates across chunk boundaries.

This is Stage 2 of the Pinpo pipeline. Takes the flat list of TranscriptLines
from the parser and groups them into overlapping chunks that fit within the
LLM's context window while maintaining coordinate integrity.
"""

from typing import List, Dict, Any
from src.models import TranscriptLine


# =========================================================================
# [BLOCK-09: TranscriptChunk — Coordinate-Tagged LLM Processing Unit]
# WHAT: A bounded window of transcript lines that will be sent to the LLM
#       as a single prompt. Contains all lines from a contiguous page range.
# WHY: Depositions can be 80+ pages (2000+ lines). Sending the entire
#      transcript to the LLM would exceed context limits and reduce quality.
#      Instead, we create overlapping chunks of ~10-12 pages each.
# KEY PROPERTIES:
#   - chunk_id: Sequential identifier (1, 2, 3, ...)
#   - start_page/end_page: Page range this chunk covers
#   - formatted_text: The LLM-ready string with [Pxx:Lxx] coordinate tags
# =========================================================================
class TranscriptChunk:
    """Represents a bounded window of transcript lines for contextual LLM processing."""

    def __init__(self, chunk_id: int, lines: List[TranscriptLine]):
        self.chunk_id = chunk_id  # Sequential chunk identifier
        self.lines = lines  # The actual TranscriptLine objects in this chunk

        # Derive coordinate bounds from the first and last lines
        self.start_page = lines[0].page if lines else 0
        self.start_line = lines[0].line if lines else 0
        self.end_page = lines[-1].page if lines else 0
        self.end_line = lines[-1].line if lines else 0

    @property
    def formatted_text(self) -> str:
        """Formats lines with explicit [Pxx:Lxx] coordinate tags.
        
        This is the text that gets sent to Gemini. The coordinate tags are
        critical because the LLM needs to report back which pages/lines
        each topic spans. Without these tags, the LLM would hallucinate coordinates.
        
        Example output:
            [P07:L12] QUESTION (PURCELL): Where did you go to law school?
            [P07:L13] ANSWER (YU): I attended NYU School of Law.
        """
        chunks = []
        for l in self.lines:
            if not l.text.strip():
                continue  # Skip blank lines to save LLM tokens
            spk_tag = f"{l.speaker}: " if l.speaker else ""
            # Zero-padded page and line numbers for consistent alignment
            chunks.append(f"[P{l.page:02d}:L{l.line:02d}] {spk_tag}{l.text}")
        return "\n".join(chunks)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes chunk metadata for logging and debugging."""
        return {
            "chunk_id": self.chunk_id,
            "start_page": self.start_page,
            "start_line": self.start_line,
            "end_page": self.end_page,
            "end_line": self.end_line,
            "line_count": len(self.lines)
        }


# =========================================================================
# [BLOCK-10: TranscriptChunker — Sliding Window with Overlap]
# WHAT: Takes the complete list of TranscriptLines and creates overlapping
#       page-based chunks for LLM processing.
# WHY: Overlap is essential to avoid "boundary split loss" — if a topic
#      discussion spans the boundary between two chunks, the overlap ensures
#      both chunks see the complete topic. The merger (BLOCK-14) later
#      deduplicates any topics that appear in both overlapping chunks.
# HOW IT WORKS:
#   1. Group all lines by their printed page number
#   2. Sort pages numerically
#   3. Create a sliding window of chunk_size_pages (default: 10-12 pages)
#   4. Advance the window by (chunk_size - overlap) pages each step
#   Example with chunk_size=10, overlap=2:
#     Chunk 1: pages 7-16
#     Chunk 2: pages 15-24  (pages 15-16 overlap with chunk 1)
#     Chunk 3: pages 23-32  (pages 23-24 overlap with chunk 2)
# PARAMETERS:
#   chunk_size_pages=10-12: Context window size in pages
#   overlap_pages=2: How many pages overlap between consecutive chunks
# =========================================================================
class TranscriptChunker:
    """Slices canonical transcript lines into overlapping page-bounded chunks."""

    def __init__(self, chunk_size_pages: int = 10, overlap_pages: int = 2):
        self.chunk_size_pages = chunk_size_pages  # How many pages per chunk
        self.overlap_pages = overlap_pages  # How many pages overlap between chunks

    def create_chunks(self, lines: List[TranscriptLine]) -> List[TranscriptChunk]:
        """
        Groups lines by printed page and produces sliding window chunks.
        Guarantees contiguous coverage with overlap to avoid boundary split loss.
        """
        if not lines:
            return []

        # Step 1: Group lines by their printed page number
        page_dict: Dict[int, List[TranscriptLine]] = {}
        for l in lines:
            page_dict.setdefault(l.page, []).append(l)

        sorted_pages = sorted(page_dict.keys())  # Sort pages numerically (7, 8, 9, ..., 88)
        chunks: List[TranscriptChunk] = []
        chunk_id = 1

        # Calculate step size: advance by (chunk_size - overlap) pages each iteration
        # With chunk_size=10 and overlap=2, step=8
        step = max(1, self.chunk_size_pages - self.overlap_pages)

        for i in range(0, len(sorted_pages), step):
            # Select the page window for this chunk
            page_window = sorted_pages[i : i + self.chunk_size_pages]
            if not page_window:
                break

            # Collect all TranscriptLines from the pages in this window
            chunk_lines: List[TranscriptLine] = []
            for p in page_window:
                chunk_lines.extend(page_dict[p])

            # Create the chunk object
            chunks.append(TranscriptChunk(chunk_id=chunk_id, lines=chunk_lines))
            chunk_id += 1

            # Stop early if we've reached the last page (no more chunks needed)
            if page_window[-1] == sorted_pages[-1]:
                break

        return chunks
