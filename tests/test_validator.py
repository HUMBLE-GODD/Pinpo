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
    Under label-only semantic validation, abstract topic labels like
    'Introduction & Ground Rules' have zero keyword overlap with the
    transcript and correctly route to human review (Pillar 3 fails).
    The test verifies that coordinate snapping STILL works even when
    the topic is flagged for review.
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
    assert validated.start_page == 7
    # Should snap directly to line 12 or 13 where Purcell introduction exists
    assert validated.start_line in [12, 13]
    # Abstract label has zero keyword overlap with transcript → Pillar 3 fails
    # → correctly flagged for human review under adversarial defense
    assert validated.needs_human_review is True
    assert validated.confidence == 0.0


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
    # Inverted boundaries fail Pillar 4 -> must be flagged for review
    assert validated.verified is False
    assert validated.confidence == 0.0
    assert validated.needs_human_review is True


def test_binary_trust_no_inconsistent_state(parser):
    """Verifies that an entry can NEVER have verified=True while needs_human_review=True."""
    validator = ProvenanceValidator(parser)
    # Entry with non-existent quote (fails Pillar 2)
    entry = TopicEntry(
        topic="CFPB Enforcement Actions",
        start_page=7,
        start_line=12,
        end_page=7,
        end_line=20,
        summary="Discussion of CFPB regulatory action.",
        supporting_quote="The CFPB issued a civil investigative demand"
    )
    validated = validator.validate_and_align(entry)
    assert not (validated.verified and validated.needs_human_review), "Cannot be verified AND need review"
    assert validated.verified is False
    assert validated.confidence == 0.0
    assert validated.needs_human_review is True


def test_aligned_end_snaps_empty_end_line(parser):
    """Verifies that aligned_end from quote grounding snaps an empty end boundary."""
    validator = ProvenanceValidator(parser)
    # End coordinate points to a blank line
    entry = TopicEntry(
        topic="Introduction & Ground Rules",
        start_page=7,
        start_line=12,
        end_page=7,
        end_line=25,  # Valid line
        summary="John Purcell explains deposition procedures.",
        supporting_quote="My name's John Purcell. I represent the defendants"
    )
    # Make end_page/end_line point to line with no text
    entry.end_line = 1  # Line 1 is typically blank
    validated = validator.validate_and_align(entry)
    assert validated.end_line >= 12  # Snapped to quote end line


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
