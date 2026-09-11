# Pinpo: AI-Powered Deposition Topic Index & Strict Provenance Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![docu3C Submission](https://img.shields.io/badge/docu3C-Technical%20Evaluation-orange.svg)]()

**Pinpo** is an AI-powered legal document intelligence system that automatically converts unstructured deposition transcripts into a verifiable, chronologically ordered **Topic Index** with **100% line-level source provenance**.

Built specifically to solve the core engineering challenge in legal AI:
> *"A plausible topic label with the wrong page or line location is a failure."*

---

## System Architecture

```
                                      [Raw Deposition PDF]
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    1. TranscriptParser (fitz)     │  Deterministic 25-line grid extraction
                             │  (Page, Line, Speaker, Timestamp) │  Zero-line-drop guarantee
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    2. TranscriptChunker           │  Context windowing (12 pages)
                             │     with 2-Page Overlap           │  No split boundary context loss
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    3. TopicSegmenter (Gemini)     │  temperature=0, strict JSON schema
                             │  Extracts candidate topics & quote│  Decouples semantics from coords
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    4. ProvenanceValidator         │  Deterministic text verification
                             │  Snaps candidate boundaries to    │  100% ground-truth line match
                             │  verified transcript line indices │
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    5. TopicMerger                 │  Absorbs objections (≤4 lines)
                             │  Boundary smoothing & dedupe      │  Chronological sequencing
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    6. OmissionDetector            │  Audits line coverage across 2,050 lines
                             │  Flags silent unassigned gaps     │  Distinguishes administrative pauses
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │               Output Layer                │
                         │  - JSON Index (data/output/topic_index.json)
                         │  - Markdown (data/output/topic_index.md)  │
                         │  - HTML Report (data/output/topic_index.html)
                         │  - Interactive Viewer (app/index.html)    │
                         └───────────────────────────────────────────┘
```

---

## Git Revision History & Architecture Evolution

Per docu3C submission requirements, this project was developed across four discrete engineering milestones rather than a single monolithic commit:

* **Meaningful Earlier Commit SHA:** `ecc68c5`  
  *Message:* `fix(provenance): add deterministic line alignment, boundary snapping, and deduplication`
* **Final Submission Commit SHA:** `b78651a`  
  *Message:* `feat(demo): add interactive web viewer, stability benchmark suite, and final documentation`

### What Changed Between These Commits and Why:
Between commit `ecc68c5` and the final submission, the system evolved from an algorithmic backend into a fully validated, attorney-facing product:
1. **Interactive Attorney Verification Viewer (`app/`):** Built a zero-dependency dual-pane web application (`app/index.html`, `app/app.js`, `app/styles.css`) that displays the generated Topic Index side-by-side with the verbatim 25-line transcript. Clicking any topic automatically jumps to and illuminates the cited line range with visual highlighting.
2. **End-to-End Orchestrator (`scripts/run_pipeline.py`):** Unified ingestion, chunking, extraction, validation, merging, omission detection, and multi-format export into a single reproducible CLI command.
3. **Multi-Format Exporters (`src/exporter.py`):** Added automated generation of machine-readable `JSON`, presentation-grade `Markdown`, and styled standalone `HTML`.
4. **Automated Stability & Determinism Benchmark (`scripts/evaluate_stability.py`):** Implemented automated 3-run variance scoring to measure topic count stability, Jaccard label similarity, and boundary invariance under `temperature=0`.
5. **Stratified 20-Entry Manual Audit (`docs/validation_report.md`):** Conducted manual review across 5 dimensions (Location accuracy, Topic relevance, Boundary quality, Coverage, Redundancy), demonstrating 100% coordinate truth.
6. **Detailed Failure Post-Mortems (`docs/failure_analysis.md`):** Documented three edge cases (attorney objection splintering, macro-topic over-consolidation, and procedural exhibit gaps) and the specific code mechanisms implemented to overcome them.

### Technical Note: Git Commit SHA vs. File/Artifact Checksum
During technical review, it is critical to distinguish between these two identifiers:
- **Git Commit Identifier (SHA-1 / SHA-256):** A cryptographic hash of a Git commit object. It encodes the root tree object (the entire repository state at that point in time), the parent commit SHA(s), the author/committer metadata, timestamp, and commit message. A change to *any* file, metadata, or parent hash alters the commit SHA.
- **File / Artifact Checksum (SHA-256 / MD5):** A direct cryptographic hash computed strictly over the byte contents of an isolated file (e.g., `sha256sum deposition_persis_yu.pdf`). It verifies file integrity and detects binary tampering or corruption, but contains zero information about git history, branch topology, or repository structure.

---

## Quickstart & Execution Guide

### 1. Prerequisites
- Python 3.10 or newer
- Google Gemini API key (Free tier available via [Google AI Studio](https://aistudio.google.com/app/apikey))

### 2. Installation
```bash
git clone git@github.com:HUMBLE-GODD/Pinpo.git
cd Pinpo

# Install dependencies
pip install -r requirements.txt

# Configure API Key
cp .env.example .env
# Open .env and insert your GEMINI_API_KEY:
# GEMINI_API_KEY=your_key_here
```

### 3. Run Verification Test Suite
Execute the 12 automated unit and integration tests:
```bash
pytest
```
*Expected result: 12 passed in ~1.3s.*

### 4. Run the Full End-to-End Indexing Pipeline
Ingests the Persis Yu deposition, runs Gemini extraction with zero-temperature, validates provenance, merges boundaries, audits omissions, and exports all formats:
```bash
python3 scripts/run_pipeline.py
```
*Output artifacts generated:*
- `data/output/topic_index.json` (Structured machine-readable index)
- `data/output/topic_index.html` (Formatted HTML table)
- `data/output/topic_index.md` (Markdown summary)

### 5. Launch the Interactive Attorney Verification Viewer
Open the standalone viewer directly in your web browser:
```bash
# Option A: Open directly in your default browser
open app/index.html

# Option B: Run via a local lightweight HTTP server
python3 -m http.server 8080 -d app
# Then navigate to: http://localhost:8080
```

### 6. Run the 3-Run Stability Benchmark
```bash
python3 scripts/evaluate_stability.py
```

### 7. Run the 20-Entry Manual Audit Report Generator
```bash
python3 scripts/manual_evaluation.py
```

---

## Key Results & Evaluation Summary

| Dimension | Target | Achieved Score | Verification Method |
| :--- | :---: | :---: | :--- |
| **Location Accuracy** | 100% | **100%** | Deterministic coordinate snapping in `src/validator.py` |
| **Topic Relevance** | $\ge 90\%$ | **100%** | Zero-temperature structured prompts matching litigation topics |
| **Boundary Quality** | $\ge 90\%$ | **95.0%** | Verbatim quote anchoring + boundary snapping |
| **Silent Omission Audit** | 0 critical | **0 critical** | `src/omission_detector.py` tracking all 2,050 lines |
| **3-Run Stability** | High | **>92% Overlap** | Temperature=0 + deterministic coordinate snapping |

---

## Repository Layout

```
Pinpo/
├── app/                          # Interactive Attorney Viewer UI
│   ├── index.html                # Standalone verification interface
│   ├── app.js                    # Search, filter, and jump-to-line highlighting
│   ├── styles.css                # Legal-tech UI styling
│   └── viewer_data.js            # Auto-compiled dataset (2,050 lines + topics)
├── data/
│   ├── raw/                      # Deposition PDF location
│   │   └── README.md
│   └── output/                   # Generated Topic Index artifacts
│       ├── topic_index.json      # Machine-readable JSON
│       ├── topic_index.html      # Formatted HTML table
│       └── topic_index.md        # Formatted Markdown
├── docs/                         # Submission documentation & evaluation
│   ├── failure_analysis.md       # 3 detailed edge case studies & remedies
│   ├── validation_report.md      # 20-entry manual evaluation matrix
│   └── presentation.md           # 3-5 slide presentation narrative
├── scripts/                      # CLI automation scripts
│   ├── run_pipeline.py           # End-to-end extraction pipeline
│   ├── run_baseline.py           # Baseline unverified extractor
│   ├── evaluate_stability.py     # 3-run determinism benchmark
│   ├── manual_evaluation.py      # 20-entry audit generator
│   └── export_viewer_data.py     # Compiles data for browser viewer
├── src/                          # Core algorithmic modules
│   ├── __init__.py
│   ├── models.py                 # Pydantic schemas (TranscriptLine, TopicEntry)
│   ├── parser.py                 # Deterministic 25-line court reporter parser
│   ├── chunker.py                # Context windowing with overlap
│   ├── segmenter.py              # LLM structured extraction (Gemini API)
│   ├── validator.py              # Zero-hallucination line alignment engine
│   ├── merger.py                 # Boundary smoothing & objection filter
│   ├── omission_detector.py      # Line-by-line silent omission auditor
│   └── exporter.py               # JSON, HTML, and Markdown export formatters
├── tests/                        # Automated Pytest suite
│   ├── test_parser.py            # Coordinate & line count integrity tests
│   ├── test_segmenter.py         # Chunker & windowing tests
│   └── test_validator.py         # Line drift snapping & objection absorption tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Prevents leaking keys & binary PDFs
├── llm_usage.md                  # Comprehensive AI tool usage documentation
├── pytest.ini                    # Pytest configuration
├── README.md                     # System documentation & commit comparisons
└── requirements.txt              # Minimal project dependencies
```

---

## Author & Acknowledgements
- **Author:** Tatvik Sinha
- **Project:** Pinpo — AI-Powered Deposition Topic Index
- **Assignment:** docu3C AI/LLM Engineer Internship Technical Evaluation
