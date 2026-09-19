"""
Legal Transcript Text Cleaner & Noise Filter.
Preprocesses deposition transcript lines to remove procedural boilerplate,
collapse repeated objections, and filter court reporter instructions
before LLM ingestion — reducing token waste and improving topic segmentation accuracy.

Uses NLTK for linguistic preprocessing (stopword-aware keyword extraction)
and domain-specific legal noise patterns.
"""

import re
from typing import List, Set

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    # Ensure required NLTK data is available
    try:
        stopwords.words('english')
    except LookupError:
        nltk.download('stopwords', quiet=True)
    try:
        word_tokenize("test")
    except LookupError:
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

from src.models import TranscriptLine


# --- Legal Noise Patterns ---

# Exact procedural phrases that carry zero topical value
PROCEDURAL_PHRASES = {
    "objection", "objection form", "objection to form",
    "objection foundation", "objection to foundation",
    "objection asked and answered", "objection relevance",
    "objection vague", "objection compound",
    "objection calls for speculation", "objection hearsay",
    "objection nonresponsive", "move to strike",
    "let the record reflect", "let me read that back",
    "can i have that read back", "please read the question back",
    "can you read that back", "read that back please",
    "off the record", "back on the record",
    "go off the record", "lets go off the record",
    "stipulated", "so stipulated", "same objection",
    "continuing objection", "standing objection",
    "noted", "noted for the record",
}

# Regex patterns for lines that are pure procedural noise
NOISE_PATTERNS = [
    re.compile(r'^\((?:exhibit|deposition exhibit)\s+(?:no\.?\s*)?\d+\s+(?:was\s+)?marked', re.IGNORECASE),
    re.compile(r'^\((?:recess|break|lunch)\s+(?:taken|had|from)', re.IGNORECASE),
    re.compile(r'^\((?:discussion|conference)\s+(?:held\s+)?off\s+the\s+record', re.IGNORECASE),
    re.compile(r'^\((?:whereupon|thereupon)', re.IGNORECASE),
    re.compile(r'^\(the\s+(?:deposition|examination|proceeding)\s+(?:was\s+)?(?:recessed|adjourned|concluded|resumed)', re.IGNORECASE),
    re.compile(r'^---+$'),
    re.compile(r'^\*\s*\*\s*\*'),
]


class TextCleaner:
    """
    Filters procedural noise from deposition transcript lines before LLM ingestion.
    
    Cleaning Strategy:
    - Tags pure objection lines as [OBJECTION] tokens (preserves coordinate, removes boilerplate text)
    - Collapses consecutive objection-only exchanges into a single marker
    - Removes court reporter procedural instructions
    - Preserves ALL substantive testimony (witness answers, attorney questions)
    - Never removes a line that contains witness testimony after an objection
    
    Uses NLTK stopwords for keyword extraction used in downstream semantic validation.
    """

    def __init__(self):
        self._stopwords: Set[str] = set()
        if NLTK_AVAILABLE:
            self._stopwords = set(stopwords.words('english'))
        else:
            # Minimal fallback stopword list
            self._stopwords = {
                'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'you', 'your',
                'he', 'she', 'it', 'its', 'they', 'them', 'their', 'this', 'that',
                'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
                'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'may', 'might', 'shall', 'can', 'a', 'an', 'the', 'and', 'but',
                'or', 'if', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'from', 'as', 'into', 'about', 'between', 'through', 'not', 'no',
                'so', 'than', 'too', 'very', 'just', 'also', 'then', 'there',
                'here', 'when', 'where', 'how', 'what', 'which', 'who', 'whom',
            }

    def clean_lines(self, lines: List[TranscriptLine]) -> List[TranscriptLine]:
        """
        Filters noise from transcript lines while preserving all substantive testimony.
        
        Returns a new list of TranscriptLine objects with noise lines cleaned.
        Original objects are NOT mutated — cleaned copies are returned.
        """
        cleaned: List[TranscriptLine] = []
        consecutive_objections = 0

        for line in lines:
            text = line.text.strip()

            # Always keep blank lines (preserves 25-line grid for coordinate integrity)
            if not text:
                cleaned.append(line)
                consecutive_objections = 0
                continue

            # Check if this is a pure procedural/objection line
            if self._is_pure_noise(text):
                consecutive_objections += 1
                # Keep the FIRST objection as a collapsed marker, skip subsequent consecutive ones
                if consecutive_objections <= 1:
                    cleaned_line = TranscriptLine(
                        global_line_id=line.global_line_id,
                        page=line.page,
                        line=line.line,
                        speaker=line.speaker,
                        text="[OBJECTION]",
                        timestamp=line.timestamp,
                        raw_text=line.raw_text
                    )
                    cleaned.append(cleaned_line)
                # else: skip (collapse consecutive objections)
                continue

            # Check regex noise patterns (exhibit markings, recess notices, etc.)
            if self._matches_noise_pattern(text):
                cleaned_line = TranscriptLine(
                    global_line_id=line.global_line_id,
                    page=line.page,
                    line=line.line,
                    speaker=line.speaker,
                    text="[PROCEDURAL]",
                    timestamp=line.timestamp,
                    raw_text=line.raw_text
                )
                cleaned.append(cleaned_line)
                consecutive_objections = 0
                continue

            # Substantive line — keep as-is
            cleaned.append(line)
            consecutive_objections = 0

        return cleaned

    def extract_keywords(self, text: str) -> List[str]:
        """
        Extracts meaningful keywords from text using NLTK tokenization and stopword removal.
        Used for semantic validation (Pillar 3) — comparing topic labels against transcript content.
        """
        if not text or not text.strip():
            return []

        # Tokenize
        if NLTK_AVAILABLE:
            tokens = word_tokenize(text.lower())
        else:
            tokens = re.findall(r'[a-z]+', text.lower())

        # Remove stopwords, short tokens, and pure numbers
        keywords = [
            t for t in tokens
            if t not in self._stopwords
            and len(t) > 2
            and not t.isdigit()
            and t.isalpha()
        ]

        return keywords

    def compute_keyword_overlap(self, text_a: str, text_b: str) -> float:
        """
        Computes keyword overlap ratio between two texts using NLTK-powered extraction.
        Returns a float between 0.0 and 1.0.
        
        Used for semantic validation: checking if a topic label + summary
        shares meaningful keywords with the actual transcript text at those coordinates.
        """
        keywords_a = set(self.extract_keywords(text_a))
        keywords_b = set(self.extract_keywords(text_b))

        if not keywords_a or not keywords_b:
            return 0.0

        intersection = keywords_a & keywords_b
        # Jaccard-like: overlap relative to the smaller set (topic label is always smaller)
        smaller = min(len(keywords_a), len(keywords_b))
        return len(intersection) / smaller if smaller > 0 else 0.0

    def _is_pure_noise(self, text: str) -> bool:
        """Checks if a line is a pure procedural objection with no substantive testimony."""
        normalized = re.sub(r'[^a-z\s]', '', text.lower()).strip()

        # Direct match against known procedural phrases
        if normalized in PROCEDURAL_PHRASES:
            return True

        # Starts with objection and contains nothing else substantive
        if normalized.startswith('objection') and len(normalized.split()) <= 5:
            return True

        # "Same objection" / "Continuing objection" pattern
        if re.match(r'^(?:same|continuing|standing)\s+objection', normalized):
            return True

        return False

    def _matches_noise_pattern(self, text: str) -> bool:
        """Checks text against regex-based noise patterns."""
        for pattern in NOISE_PATTERNS:
            if pattern.search(text):
                return True
        return False
