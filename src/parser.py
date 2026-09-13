"""
Deterministic Canonical Deposition Transcript Parser.
Extracts page and line coordinates, speaker tags, timestamps, and speech text
from standard 25-line court reporter deposition transcripts with 100% provenance integrity.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import fitz  # PyMuPDF

from src.models import TranscriptLine


class TranscriptParser:
    """
    Parses court reporter deposition PDFs into a canonical, indexed line-by-line model.
    Guarantees zero dropped lines and preserves exact (page, line) coordinates.
    """

    SPEAKER_PATTERN = re.compile(
        r'^(?:BY\s+)?(MR\.\s+[A-Z]+|MS\.\s+[A-Z]+|THE\s+WITNESS|THE\s+REPORTER|THE\s+VIDEOGRAPHER|THE\s+COURT|Q\b|A\b)[\.:\s]*(.*)',
        re.IGNORECASE
    )
    TIMESTAMP_PATTERN = re.compile(r'(\d{2}:\d{2})\s*$')
    PAGE_FOOTER_PATTERN = re.compile(r'Page\s+(\d+)', re.IGNORECASE)

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"Deposition transcript not found at: {self.pdf_path}")
        
        self.lines: List[TranscriptLine] = []
        self._line_map: Dict[Tuple[int, int], TranscriptLine] = {}
        self._global_map: Dict[int, TranscriptLine] = {}

    def parse(self, start_page: int = 7, end_page: int = 88) -> List[TranscriptLine]:
        """
        Extracts substantive deposition testimony across the specified page range.
        Default range (7 to 88) captures the sworn examination of Persis Yu,
        deliberately excluding trailing court reporter errata, certificates, and concordance index.
        """
        doc = fitz.open(self.pdf_path)
        self.lines = []
        self._line_map = {}
        self._global_map = {}

        global_id = 1
        active_speaker = ""

        # Substantive testimony in Persis Yu PDF spans 1-based PDF pages 7 to 88 (indices 6 to 87).
        # Use end_page parameter to determine ceiling, with buffer for page numbering offset.
        max_pdf_index = min(len(doc), end_page + 5)

        for page_idx in range(max_pdf_index):
            page = doc[page_idx]
            page_text = page.get_text()

            # Stop if we reach the post-testimony certificate pages
            if "CERTIFICATE OF CERTIFIED SHORTHAND REPORTER" in page_text.upper() or \
               "CERTIFICATION OF CERTIFIED SHORTHAND REPORTER" in page_text.upper():
                break

            # Determine printed transcript page number
            footer_match = self.PAGE_FOOTER_PATTERN.findall(page_text)
            printed_page = int(footer_match[-1]) if footer_match else (page_idx + 1)

            # Filter to requested substantive examination window
            if printed_page < start_page or printed_page > end_page:
                continue

            # Extract blocks from page
            blocks = page.get_text("blocks")
            page_lines_dict: Dict[int, str] = {}

            for b in blocks:
                text = b[4].strip()
                if self.PAGE_FOOTER_PATTERN.match(text):
                    continue
                block_lines = [l.strip() for l in text.split('\n') if l.strip()]
                if not block_lines:
                    continue

                # The first token is the line number (1..25)
                if re.match(r'^\d+$', block_lines[0]):
                    line_no = int(block_lines[0])
                    if 1 <= line_no <= 25:
                        content = ' '.join(block_lines[1:]) if len(block_lines) > 1 else ''
                        page_lines_dict[line_no] = content

            # Guarantee all lines 1..25 are represented (even if blank)
            for line_no in range(1, 26):
                raw_content = page_lines_dict.get(line_no, "")
                speaker, clean_text, timestamp = self._parse_line_content(raw_content)

                # Maintain speaker continuity if line is continuation
                if speaker:
                    active_speaker = speaker
                elif clean_text and not active_speaker:
                    active_speaker = "EXAMINATION"

                t_line = TranscriptLine(
                    global_line_id=global_id,
                    page=printed_page,
                    line=line_no,
                    speaker=speaker or active_speaker,
                    text=clean_text,
                    timestamp=timestamp,
                    raw_text=raw_content
                )

                self.lines.append(t_line)
                self._line_map[(printed_page, line_no)] = t_line
                self._global_map[global_id] = t_line
                global_id += 1

        doc.close()
        return self.lines

    def _parse_line_content(self, raw: str) -> Tuple[str, str, Optional[str]]:
        """Separates speaker prefix, cleaned text, and timestamp from raw text."""
        if not raw:
            return "", "", None

        # Extract timestamp
        ts_match = self.TIMESTAMP_PATTERN.search(raw)
        timestamp = ts_match.group(1) if ts_match else None
        cleaned = self.TIMESTAMP_PATTERN.sub('', raw).strip()

        # Extract speaker
        spk_match = self.SPEAKER_PATTERN.match(cleaned)
        if spk_match:
            speaker = spk_match.group(1).upper()
            # Standardize Q and A prefixes
            if speaker == "Q":
                speaker = "QUESTION (PURCELL)"
            elif speaker == "A":
                speaker = "ANSWER (YU)"
            text = spk_match.group(2).strip()
            return speaker, text, timestamp

        return "", cleaned, timestamp

    def get_line(self, page: int, line: int) -> Optional[TranscriptLine]:
        """Direct coordinate lookup."""
        return self._line_map.get((page, line))

    def get_global(self, global_id: int) -> Optional[TranscriptLine]:
        """Global sequential ID lookup."""
        return self._global_map.get(global_id)

    def get_range(self, start_page: int, start_line: int, end_page: int, end_line: int) -> List[TranscriptLine]:
        """Returns all canonical lines between start and end coordinates (inclusive)."""
        selected = []
        for l in self.lines:
            if (l.page > start_page or (l.page == start_page and l.line >= start_line)) and \
               (l.page < end_page or (l.page == end_page and l.line <= end_line)):
                selected.append(l)
        return selected

    def to_compact_text(self, lines: Optional[List[TranscriptLine]] = None) -> str:
        """
        Formats transcript lines into a clean, token-efficient representation
        suitable for LLM ingestion while preserving strict line tags.
        Example: [P12:L04] Q: Where did you go to law school?
        """
        target = lines if lines is not None else self.lines
        output_lines = []
        for l in target:
            if not l.text.strip():
                continue
            spk_tag = f"{l.speaker}: " if l.speaker else ""
            output_lines.append(f"[P{l.page:02d}:L{l.line:02d}] {spk_tag}{l.text}")
        return "\n".join(output_lines)
