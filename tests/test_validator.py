"""
Unit tests for ProvenanceValidator, TopicMerger, and OmissionDetector.
"""

import pytest
from src.parser import TranscriptParser
from src.models import TopicEntry, TranscriptLine
from src.validator import ProvenanceValidator
from src.merger import TopicMerger
from src.omission_detector import OmissionDetector

PDF_PATH = "data/raw/deposition_persis_yu.pdf"


@pytest.fixture
def parser():
    p = TranscriptParser(PDF_PATH)
    p.parse(start_page=7, end_page=10)
    return p


def test_validator_snaps_line_drift(parser):
    """
    If the LLM provides an approximate or off-by-2 line number,
    the validator must locate the quote and snap the boundary to ground truth.
    """
    validator = ProvenanceValidator(parser)

    # Simulated drifted LLM output: claimed start line was 8 instead of line 12
    drifted_entry = TopicEntry(
        topic="Introduction & Ground Rules",
        start_page=7,
        start_line=8,
        end_page=7,
        end_line=20,
        summary="Introduction by Mr. Purcell.",
        supporting_quote="My name's John Purcell. I represent the defendants"
    )

    validated = validator.validate_and_align(drifted_entry)
    assert validated.verified is True
    assert validated.start_page == 7
    # Should snap directly to line 12 or 13 where Purcell introduction exists
    assert validated.start_line in [12, 13]
    assert validated.confidence >= 0.85


def test_validator_inversion_correction(parser):
    """Verifies that inverted start/end coordinates are automatically corrected."""
    validator = ProvenanceValidator(parser)
    inverted_entry = TopicEntry(
        topic="Test",
        start_page=8,
        start_line=15,
        end_page=7,
        end_line=12,
        supporting_quote="Yes, I do"
    )
    validated = validator.validate_and_align(inverted_entry)
    assert validated.start_page <= validated.end_page


def test_merger_combines_similar_adjacent_topics():
    """Verifies that cross-chunk duplicates or adjacent pieces merge cleanly."""
    merger = TopicMerger(title_similarity_threshold=0.70)
    entries = [
        TopicEntry(
            topic="Witness Background and Retainer",
            start_page=8,
            start_line=24,
            end_page=9,
            end_line=10,
            summary="Retained as expert."
        ),
        TopicEntry(
            topic="Witness Background & Role",
            start_page=9,
            start_line=8,
            end_page=9,
            end_line=25,
            summary="Asked to provide historical context."
        )
    ]
    merged = merger.merge(entries)
    assert len(merged) == 1
    assert merged[0].start_page == 8
    assert merged[0].end_page == 9
    assert merged[0].end_line == 25


def test_merger_absorbs_short_objections():
    """Verifies that a 2-line attorney objection is absorbed into the parent topic."""
    merger = TopicMerger()
    entries = [
        TopicEntry(
            topic="Department of Education Consultation",
            start_page=12,
            start_line=1,
            end_page=12,
            end_line=18,
            summary="Policy memo review."
        ),
        TopicEntry(
            topic="Attorney Objection",
            start_page=12,
            start_line=19,
            end_page=12,
            end_line=20,
            summary="Objection to form."
        )
    ]
    merged = merger.merge(entries)
    assert len(merged) == 1
    assert merged[0].end_line == 20


def test_omission_detector_audit(parser):
    """Verifies that omission detector tracks lines and reports coverage."""
    canonical_lines = parser.lines
    detector = OmissionDetector(canonical_lines)

    topics = [
        TopicEntry(
            topic="Opening Examination",
            start_page=7,
            start_line=1,
            end_page=10,
            end_line=25
        )
    ]
    report = detector.audit(topics)
    assert report.total_lines == len(canonical_lines)
    assert report.coverage_percentage == 100.0
    assert report.has_critical_omissions is False
