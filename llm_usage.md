# AI / LLM Usage Documentation (`llm_usage.md`)

This document records the transparent use of AI coding assistants and LLMs during the development of **Pinpo**, per docu3C technical evaluation guidelines.

---

## 1. What AI Was Used For
- **Architectural Brainstorming & Tradeoff Analysis:** Evaluating approaches for legal topic segmentation (sliding window vs. hierarchical vs. full-document context window).
- **Coordinate Grid Layout Modeling:** Identifying court-reporter page-coordinate layout patterns (25-line grid, timestamp positions, speaker attribution conventions).
- **Test Scaffolding & Pytest Fixtures:** Generating comprehensive test cases to verify coordinate indexing integrity.

---

## 2. Key AI Suggestions: Accepted, Modified, and Rejected

### Accepted:
- **PyMuPDF (`fitz`) Text-Block Coordinate Parsing:** AI suggested using bounding box blocks rather than naive raw text regex to maintain strict (x, y) spatial grid alignment for lines 1–25.
- **Pydantic V2 Schemas:** Adopted structured schemas for `TranscriptLine`, `TopicEntry`, and `TopicIndex` to enforce strict validation.

### Modified:
- **Speaker Attribution Regex:** AI suggested a simple `Q:` and `A:` prefix splitter. In actual legal transcripts, examining attorneys frequently use `BY MR. PURCELL:` followed by `Q.`, and objections are entered by `MR. BLOOD:` or `THE WITNESS:`. We expanded and hardened the speaker regex to capture court-reporter nuances and maintain continuity across multi-line answers.
- **Concordance Index Isolation:** AI initially parsed the full PDF without bounding the substantive testimony range. In the Persis Yu deposition, the trailing word concordance index (pages 94–122) re-numbers pages starting from 1. We modified the parser logic to cap substantive extraction at Page 88 before the reporter certification and errata sheet.

### Rejected:
- **Letting LLMs Guess Page and Line Numbers:** Rejected a naive prompt design where an LLM is asked to output `start_line` and `end_line` purely from generation memory. Because LLMs hallucinate numeric indices, we strictly mandated a **deterministic line alignment engine** where the LLM only outputs candidate quote anchors and Python verifies the exact line indices against the canonical transcript.

---

## 3. How AI-Generated Work Was Validated
- **Deterministic Automated Testing:** Created `tests/test_parser.py` ensuring that all 82 substantive examination pages (Pages 7 to 88) have exactly 25 lines parsed ($82 \times 25 = 2050$ lines) with zero dropped lines.
- **Ground-Truth Verification:** Hand-verified key anchors (Page 7 Line 12 opening question by Mr. Purcell; Page 8 Line 2 witness answer; Page 88 Line 13 conclusion).
