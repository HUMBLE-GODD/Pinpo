"""
Transcript Chunker with coordinate-aware windowing and overlap.
Divides canonical transcript lines into contextual segments for LLM processing,
preserving page and line coordinates across chunk boundaries.
"""

from typing import List, Dict, Any
from src.models import TranscriptLine


class TranscriptChunk:
    """Represents a bounded window of transcript lines for contextual LLM processing."""
    def __init__(self, chunk_id: int, lines: List[TranscriptLine]):
        self.chunk_id = chunk_id
        self.lines = lines
        self.start_page = lines[0].page if lines else 0
        self.start_line = lines[0].line if lines else 0
        self.end_page = lines[-1].page if lines else 0
        self.end_line = lines[-1].line if lines else 0

    @property
    def formatted_text(self) -> str:
        """Formats lines with explicit [Pxx:Lxx] coordinate tags."""
        chunks = []
        for l in self.lines:
            if not l.text.strip():
                continue
            spk_tag = f"{l.speaker}: " if l.speaker else ""
            chunks.append(f"[P{l.page:02d}:L{l.line:02d}] {spk_tag}{l.text}")
        return "\n".join(chunks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "start_page": self.start_page,
            "start_line": self.start_line,
            "end_page": self.end_page,
            "end_line": self.end_line,
            "line_count": len(self.lines)
        }


class TranscriptChunker:
    """Slices canonical transcript lines into overlapping page-bounded chunks."""

    def __init__(self, chunk_size_pages: int = 10, overlap_pages: int = 2):
        self.chunk_size_pages = chunk_size_pages
        self.overlap_pages = overlap_pages

    def create_chunks(self, lines: List[TranscriptLine]) -> List[TranscriptChunk]:
        """
        Groups lines by printed page and produces sliding window chunks.
        Guarantees contiguous coverage with overlap to avoid boundary split loss.
        """
        if not lines:
            return []

        # Group lines by page
        page_dict: Dict[int, List[TranscriptLine]] = {}
        for l in lines:
            page_dict.setdefault(l.page, []).append(l)

        sorted_pages = sorted(page_dict.keys())
        chunks: List[TranscriptChunk] = []
        chunk_id = 1
        step = max(1, self.chunk_size_pages - self.overlap_pages)

        for i in range(0, len(sorted_pages), step):
            page_window = sorted_pages[i : i + self.chunk_size_pages]
            if not page_window:
                break

            chunk_lines: List[TranscriptLine] = []
            for p in page_window:
                chunk_lines.extend(page_dict[p])

            chunks.append(TranscriptChunk(chunk_id=chunk_id, lines=chunk_lines))
            chunk_id += 1

            # If the current window reached the last page, finish
            if page_window[-1] == sorted_pages[-1]:
                break

        return chunks
