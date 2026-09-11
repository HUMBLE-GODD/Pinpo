# AI / LLM Usage Documentation (`llm_usage.md`)

This document records the transparent use of AI coding assistants and LLMs during the development of **Pinpo**, per docu3C technical evaluation guidelines.

---

## 1. What AI Was Used For
- **Architectural Brainstorming & Tradeoff Analysis:** Evaluating approaches for legal topic segmentation (sliding window vs. hierarchical vs. full-document context window).
- **Coordinate Grid Layout Modeling:** Identifying court-reporter page-coordinate layout patterns (25-line grid, timestamp positions, speaker attribution conventions).
- **Test Scaffolding & Pytest Fixtures:** Generating comprehensive test cases to verify coordinate indexing integrity.
- **LLM Prompt Engineering & System Directives:** Crafting zero-temperature, JSON-mode prompts for Gemini to segment multi-turn deposition Q&A dialogue.
- **Sequence Matching & Boundary Snapping Algorithms:** Designing deterministic string alignment algorithms to bridge generative LLM outputs with raw transcript lines.

---

## 2. Key AI Suggestions: Accepted, Modified, and Rejected

### Accepted:
- **PyMuPDF (`fitz`) Text-Block Coordinate Parsing:** AI suggested using bounding box blocks rather than naive raw text regex to maintain strict (x, y) spatial grid alignment for lines 1–25.
- **Pydantic V2 Schemas:** Adopted structured schemas for `TranscriptLine`, `TopicEntry`, and `TopicIndex` to enforce strict validation.
- **Coordinate Tag Prefixing:** Tagging every line fed to the LLM with `[Pxx:Lxx]` to ground the model's attention on exact page and line numbers.

### Modified:
- **Speaker Attribution Regex:** AI suggested a simple `Q:` and `A:` prefix splitter. In actual legal transcripts, examining attorneys frequently use `BY MR. PURCELL:` followed by `Q.`, and objections are entered by `MR. BLOOD:` or `THE WITNESS:`. We expanded and hardened the speaker regex to capture court-reporter nuances and maintain continuity across multi-line answers.
- **Concordance Index Isolation:** AI initially parsed the full PDF without bounding the substantive testimony range. In the Persis Yu deposition, the trailing word concordance index (pages 94–122) re-numbers pages starting from 1. We modified the parser logic to cap substantive extraction at Page 88 before the reporter certification and errata sheet.
- **Rate-Limiting & Exponential Backoff:** Added 1-second pacing and automatic exponential backoff retry on HTTP 429 to cleanly handle free-tier API quotas.
- **Substring Matching Guardrails:** When designing the quote locator, AI generated a standard `if window in quote: ratio = 1.0`. When tested against blank lines (`window = ""`), Python's default behavior evaluated `"" in quote` as `True`, causing blank lines to snap falsely. We modified the validator with strict non-empty and minimum length (`>= 5` chars) thresholds.

### Rejected:
- **Letting LLMs Guess Page and Line Numbers:** Rejected a naive prompt design where an LLM is asked to output `start_line` and `end_line` purely from generation memory. Because LLMs hallucinate numeric indices, we strictly mandated a **deterministic line alignment engine** (`src/validator.py`) where the LLM only outputs candidate quote anchors and Python verifies the exact line indices against the canonical transcript.
- **Allowing LLMs to Decide Omission:** Rejected asking the LLM if it missed any sections. Built `src/omission_detector.py` to audit line indices mathematically against the canonical 2,050 line array.

---

## 3. How AI-Generated Work Was Validated
- **Deterministic Automated Testing:** Created `tests/test_parser.py`, `tests/test_segmenter.py`, and `tests/test_validator.py` ensuring zero dropped lines, verified boundary snapping, and complete omission detection.
- **Drift Simulation Testing:** Specifically tested off-by-2 line errors in `test_validator_snaps_line_drift` to prove that the validator snaps drifted boundaries back to ground-truth coordinates.
- **Ground-Truth Verification:** Hand-verified key anchors (Page 7 Line 12 opening question by Mr. Purcell; Page 8 Line 2 witness answer; Page 88 Line 13 conclusion).
