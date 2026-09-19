"""
Tests for TextCleaner — document cleaning, NLTK keyword extraction, and semantic validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cleaner import TextCleaner
from src.models import TranscriptLine


def _make_line(global_id, page, line, speaker, text):
    return TranscriptLine(
        global_line_id=global_id, page=page, line=line,
        speaker=speaker, text=text, raw_text=text
    )


class TestTextCleaner:
    def setup_method(self):
        self.cleaner = TextCleaner()

    # --- Document Cleaning Tests ---

    def test_keeps_substantive_testimony(self):
        """Substantive Q&A lines should pass through unchanged."""
        lines = [
            _make_line(1, 7, 1, "QUESTION (PURCELL)", "Where did you go to law school?"),
            _make_line(2, 7, 2, "ANSWER (YU)", "I attended NYU School of Law."),
        ]
        cleaned = self.cleaner.clean_lines(lines)
        assert len(cleaned) == 2
        assert cleaned[0].text == "Where did you go to law school?"
        assert cleaned[1].text == "I attended NYU School of Law."

    def test_collapses_consecutive_objections(self):
        """Multiple consecutive objection lines should collapse to a single [OBJECTION] marker."""
        lines = [
            _make_line(1, 10, 1, "QUESTION (PURCELL)", "What was the loan amount?"),
            _make_line(2, 10, 2, "MR. SMITH", "Objection. Form."),
            _make_line(3, 10, 3, "MR. JONES", "Same objection."),
            _make_line(4, 10, 4, "MR. SMITH", "Objection to form"),
            _make_line(5, 10, 5, "ANSWER (YU)", "It was approximately fifty thousand dollars."),
        ]
        cleaned = self.cleaner.clean_lines(lines)
        # Should keep: question, ONE objection marker, answer = 3 lines
        texts = [l.text for l in cleaned]
        assert texts[0] == "What was the loan amount?"
        assert texts[1] == "[OBJECTION]"
        assert texts[-1] == "It was approximately fifty thousand dollars."
        # The 3 consecutive objections should collapse to just 1
        assert texts.count("[OBJECTION]") == 1

    def test_tags_procedural_noise(self):
        """Exhibit markings and recess notations should be tagged as [PROCEDURAL]."""
        lines = [
            _make_line(1, 15, 1, "", "(Exhibit No. 7 was marked for identification)"),
            _make_line(2, 15, 2, "", "(Recess taken from 10:30 a.m.)"),
        ]
        cleaned = self.cleaner.clean_lines(lines)
        assert cleaned[0].text == "[PROCEDURAL]"
        assert cleaned[1].text == "[PROCEDURAL]"

    def test_preserves_blank_lines(self):
        """Blank lines must be preserved for 25-line grid coordinate integrity."""
        lines = [
            _make_line(1, 7, 1, "", ""),
            _make_line(2, 7, 2, "QUESTION (PURCELL)", "Good morning."),
            _make_line(3, 7, 3, "", ""),
        ]
        cleaned = self.cleaner.clean_lines(lines)
        assert len(cleaned) == 3
        assert cleaned[0].text == ""
        assert cleaned[2].text == ""

    def test_preserves_testimony_after_objection(self):
        """A witness answer on the same line as an objection concept should NOT be removed."""
        lines = [
            _make_line(1, 20, 1, "ANSWER (YU)", "I don't recall the specific date but it was around March."),
        ]
        cleaned = self.cleaner.clean_lines(lines)
        assert cleaned[0].text == "I don't recall the specific date but it was around March."

    # --- NLTK Keyword Extraction Tests ---

    def test_extract_keywords_removes_stopwords(self):
        """Keywords should exclude common stopwords like 'the', 'and', 'is'."""
        keywords = self.cleaner.extract_keywords("The student loan was originated by the bank")
        assert "the" not in keywords
        assert "was" not in keywords
        assert "student" in keywords
        assert "loan" in keywords
        assert "bank" in keywords

    def test_extract_keywords_empty_input(self):
        """Empty or whitespace-only input should return empty list."""
        assert self.cleaner.extract_keywords("") == []
        assert self.cleaner.extract_keywords("   ") == []

    # --- Semantic Validation (Keyword Overlap) Tests ---

    def test_keyword_overlap_matching_content(self):
        """Topic label and related transcript text should have high keyword overlap."""
        topic = "Student Loan Origination Practices"
        transcript = "We discussed the student loan origination practices at ITT and how loans were originated by the institution"
        score = self.cleaner.compute_keyword_overlap(topic, transcript)
        assert score >= 0.5, f"Expected high overlap for matching content, got {score}"

    def test_keyword_overlap_mismatched_content(self):
        """Topic label and unrelated transcript text should have low keyword overlap."""
        topic = "Educational Background & Degrees"
        transcript = "The enforcement action was filed by the CFPB against the servicer for violations of the consumer financial protection act"
        score = self.cleaner.compute_keyword_overlap(topic, transcript)
        assert score < 0.5, f"Expected low overlap for mismatched content, got {score}"

    def test_keyword_overlap_empty_input(self):
        """Empty input should return 0.0 overlap."""
        assert self.cleaner.compute_keyword_overlap("", "some text") == 0.0
        assert self.cleaner.compute_keyword_overlap("some text", "") == 0.0
