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
                             │  (Page, Line, Speaker, Timestamp) │  Zero-line-drop guarantee & metadata
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    2. TranscriptChunker           │  Context windowing (12 pages)
                             │     with 2-Page Overlap           │  Explicit [Pxx:Lxx] coordinate tags
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    3. TextCleaner (NLTK)          │  Collapses repeated objections
                             │  Boilerplate & Noise Reduction    │  Cuts tokens 15–20% to prevent hallucinations
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    4. TopicSegmenter (Gemini)     │  Metadata-aware prompt injection
                             │  temperature=0, strict JSON schema│  4-model automatic fallback cascade
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    5. ProvenanceValidator         │  4-Pillar Verification (Coords, Quote,
                             │  Snaps boundaries & verifies text │  Semantic, Boundary) + Binary Trust
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    6. TopicMerger                 │  Absorbs objections (≤4 lines)
                             │  Boundary smoothing & dedupe      │  Chronological sequencing
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────┐
                             │    7. OmissionDetector            │  Audits line coverage across 2,050 lines
                             │  Flags silent unassigned gaps     │  Distinguishes administrative pauses
                             └─────────────────┬─────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │               Output Layer                │
                         │  - JSON Index (data/output/topic_index.json)
                         │  - Markdown (data/output/topic_index.md)  │
                         │  - HTML Report (data/output/topic_index.html)
                         │  - Interactive Dual-Pane Web Viewer       │
                         └───────────────────────────────────────────┘
```

---

## Git Revision History & Architecture Evolution

Per docu3C submission requirements, this project was developed across four discrete engineering milestones rather than a single monolithic commit:

* **Meaningful Earlier Commit SHA:** `ecc68c5`  
  *Message:* `fix(provenance): add deterministic line alignment, boundary snapping, and deduplication`
* **Final Submission Commit SHA:** `cbd12ea`  
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
Execute the 28 automated unit and integration tests (covering canonical parsing, NLTK text cleaning, window chunking, 4-pillar validation, and server upload handlers):
```bash
pytest -v
```
*Expected result: 28 passed in ~2.0s.*

### 4. Run the Full End-to-End Indexing Pipeline
Ingests any court-reporter deposition PDF, automatically detects examination start/end boundaries, extracts topics with Gemini at zero-temperature, validates line provenance, merges boundaries, audits omissions, and exports all formats:
```bash
# Process default Persis Yu deposition:
python3 scripts/run_pipeline.py

# Process ANY other deposition PDF with automatic boundary & metadata detection:
python3 scripts/run_pipeline.py --pdf /path/to/any_deposition.pdf --update-viewer

# Optional: override bounds or limit to first N pages:
python3 scripts/run_pipeline.py --pdf /path/to/any_deposition.pdf --max-pages 10 --update-viewer
```
*Output artifacts generated:*
- `data/output/topic_index.json` (Structured machine-readable index)
- `data/output/topic_index.html` (Formatted HTML table)
- `data/output/topic_index.md` (Markdown summary)

### 5. Launch the Full-Stack Interactive Web Application
Run the local full-stack server to serve the viewer and enable direct PDF uploads:
```bash
# Start the full-stack server (serves UI and processes uploaded PDFs):
python3 server.py 8080
# Navigate to: http://localhost:8080
# Click "Upload PDF" to drag & drop any court reporter deposition PDF!

# Option B: Access the Static Cloud Demo (GitHub Pages)
# https://humble-godd.github.io/Pinpo/app/
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
| **Topic Relevance** | >= 90% | **100%** | Metadata-aware structured prompts matching litigation topics |
| **Boundary Quality** | >= 90% | **95.0%** | Verbatim quote anchoring + boundary snapping |
| **Topic Coverage** | High | **48 topics** | All major examination areas indexed across 82 substantive pages |
| **Line Coverage** | High | **61.5%** | Gaps are transitional/procedural lines, not substantive testimony |
| **Redundancy** | <= 5% | **0%** | Coordinate-overlap deduplication + title similarity merge |
| **3-Run Stability** | High | **Deterministic** | Temperature=0 + deterministic coordinate snapping |
| **Automation Rate** | >= 90% | **93.8%** | 45 of 48 topics certified at 100% mathematical provenance |
| **Binary Trust** | 100% | **100% / Review** | Strictly 1.0 or flagged `needs_human_review = True` |

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
│   ├── run_pipeline.py           # 7-stage end-to-end extraction pipeline
│   ├── run_baseline.py           # Baseline unverified extractor
│   ├── evaluate_stability.py     # 3-run determinism benchmark
│   ├── manual_evaluation.py      # 20-entry audit generator
│   └── export_viewer_data.py     # Compiles data for browser viewer
├── src/                          # Core algorithmic modules
│   ├── __init__.py
│   ├── models.py                 # Pydantic schemas (TranscriptLine, TopicEntry)
│   ├── parser.py                 # Deterministic 25-line court reporter parser
│   ├── chunker.py                # Context windowing with overlap
│   ├── cleaner.py                # TextCleaner (NLTK noise & objection filter)
│   ├── segmenter.py              # LLM structured extraction (Gemini API)
│   ├── validator.py              # 4-Pillar Zero-Hallucination validation engine
│   ├── merger.py                 # Boundary smoothing & objection filter
│   ├── omission_detector.py      # Line-by-line silent omission auditor
│   └── exporter.py               # JSON, HTML, and Markdown export formatters
├── tests/                        # Automated Pytest suite (28 tests)
│   ├── test_parser.py            # Coordinate & line count integrity tests
│   ├── test_cleaner.py           # TextCleaner & NLTK keyword tests
│   ├── test_segmenter.py         # Chunker & windowing tests
│   ├── test_validator.py         # Line drift snapping & objection absorption tests
│   └── test_server.py            # Server endpoint & upload validation tests
├── server.py                     # Zero-framework full-stack server & upload handler
├── .env.example                  # Environment configuration template
├── .gitignore                    # Prevents leaking keys, uploads & private files
├── llm_usage.md                  # Comprehensive AI tool usage documentation
├── pytest.ini                    # Pytest configuration
├── README.md                     # System documentation & commit comparisons
└── requirements.txt              # Project dependencies (including NLTK)
```

---

## Author & Acknowledgements
- **Author:** Tatvik Sinha
- **Project:** Pinpo — AI-Powered Deposition Topic Index
- **Assignment:** docu3C AI/LLM Engineer Internship Technical Evaluation
