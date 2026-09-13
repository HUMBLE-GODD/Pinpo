"""
Unit tests for the canonical transcript parser.
Validates zero-line-drop guarantees and coordinate integrity.
"""

import pytest
from pathlib import Path
from src.parser import TranscriptParser

PDF_PATH = "data/raw/deposition_persis_yu.pdf"


@pytest.fixture
def parser():
    assert Path(PDF_PATH).exists(), f"Required test file {PDF_PATH} missing."
    return TranscriptParser(PDF_PATH)


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        TranscriptParser("non_existent_file.pdf")


def test_substantive_line_count(parser):
    """Verifies that all 82 substantive pages (7 to 88) have exactly 25 lines parsed = 2050 lines."""
    lines = parser.parse(start_page=7, end_page=88)
    expected_count = (88 - 7 + 1) * 25
    assert len(lines) == expected_count, f"Expected {expected_count} lines, got {len(lines)}"
    assert lines[0].global_line_id == 1
    assert lines[-1].global_line_id == expected_count


def test_specific_line_coordinates(parser):
    """Verifies known ground-truth lines in the Persis Yu deposition."""
    parser.parse(start_page=7, end_page=88)

    # Page 7, Line 12 is the opening question by Mr. Purcell
    p7_l12 = parser.get_line(page=7, line=12)
    assert p7_l12 is not None
    assert "John Purcell" in p7_l12.text
    assert p7_l12.timestamp == "01:17"

    # Page 8, Line 2 is Persis Yu answering "Yes, I do."
    p8_l2 = parser.get_line(page=8, line=2)
    assert p8_l2 is not None
    assert "Yes, I do" in p8_l2.text

    # Page 88, Line 13 is the conclusion of testimony
    p88_l13 = parser.get_line(page=88, line=13)
    assert p88_l13 is not None
    assert "Persis Yu" in p88_l13.text


def test_range_extraction(parser):
    """Verifies coordinate range queries."""
    parser.parse(start_page=7, end_page=88)
    segment = parser.get_range(start_page=7, start_line=11, end_page=7, end_line=15)
    assert len(segment) == 5
    assert segment[0].line == 11
    assert segment[-1].line == 15


def test_compact_text_tagging(parser):
    """Verifies that LLM-ready compact text contains unambiguous coordinates."""
    parser.parse(start_page=7, end_page=8)
    compact = parser.to_compact_text()
    assert "[P07:L12]" in compact
    assert "[P08:L02]" in compact


def test_auto_detect_bounds(parser):
    """Verifies that auto_detect_bounds automatically identifies start and end pages."""
    start, end = parser.auto_detect_bounds()
    assert start == 7, f"Expected start page 7, got {start}"
    assert end == 88, f"Expected end page 88, got {end}"


def test_extract_metadata(parser):
    """Verifies automatic metadata extraction from preliminary pages."""
    meta = parser.extract_metadata()
    assert "witness" in meta
    assert "Persis Yu" in meta["witness"]
    assert "case_name" in meta
    assert "date" in meta


def test_parse_with_auto_detect(parser):
    """Verifies that parse() without explicit start/end page uses auto-detected bounds."""
    lines = parser.parse(start_page=None, end_page=None)
    expected_count = (88 - 7 + 1) * 25
    assert len(lines) == expected_count
    assert lines[0].page == 7
    assert lines[-1].page == 88
