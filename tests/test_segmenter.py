"""
Unit tests for TranscriptChunker and Segmenter components.
"""

import pytest
from src.parser import TranscriptParser
from src.chunker import TranscriptChunker, TranscriptChunk
from src.models import TranscriptLine

PDF_PATH = "data/raw/deposition_persis_yu.pdf"


@pytest.fixture
def sample_lines():
    parser = TranscriptParser(PDF_PATH)
    return parser.parse(start_page=7, end_page=20)


def test_chunker_coverage(sample_lines):
    """Verifies that chunker covers all requested pages without gaps."""
    chunker = TranscriptChunker(chunk_size_pages=5, overlap_pages=1)
    chunks = chunker.create_chunks(sample_lines)

    assert len(chunks) >= 3
    assert chunks[0].start_page == 7
    assert chunks[-1].end_page == 20

    # Ensure formatted text has [Pxx:Lxx] tags
    assert "[P07:L" in chunks[0].formatted_text


def test_chunk_to_dict():
    lines = [
        TranscriptLine(global_line_id=1, page=7, line=12, speaker="Q", text="Hello", raw_text="Q Hello")
    ]
    chunk = TranscriptChunk(chunk_id=1, lines=lines)
    d = chunk.to_dict()
    assert d["chunk_id"] == 1
    assert d["start_page"] == 7
    assert d["end_page"] == 7
