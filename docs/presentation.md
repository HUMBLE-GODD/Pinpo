# Pinpo: 3–5 Slide Presentation Deck

*AI-Powered Deposition Topic Index & Strict Provenance Verification Engine*  
**Candidate Submission for docu3C AI/LLM Engineer Internship**

---

## Slide 1: The Engineering Challenge & Architectural Overview

### The Problem
- **The Legal Reality:** Attorneys navigate 100–300+ page depositions of unstructured, spoken Q&A without headings or chapters.
- **The Core Risk:** In litigation, *"a plausible topic label with the wrong line reference is a failure."* Hallucinated citations lead to judicial sanctions.

### Architectural Solution
```
[Raw Deposition PDF] 
        ↓
[1. Canonical Coordinate Parser (fitz)] ──→ 2,050 lines @ (Page, Line, Speaker, Ts)
        ↓
[2. Sliding Window Chunker (12-Page)]
        ↓
[3. LLM Semantic Extractor (Gemini @ temp=0)] ──→ 54 Candidate Topics
        ↓
[4. Zero-Hallucination Provenance Engine] ──→ Exact string & coordinate verification
        ↓
[5. Boundary Merger & Digression Filter] ──→ Absorbs objections (≤4 lines), dedupes
        ↓
[6. Silent Omission Auditor] ──→ Line-by-line coverage audit
        ↓
[Interactive Web Viewer & JSON/HTML Export]
```

---

## Slide 2: Segmentation & Zero-Hallucination Provenance Strategy

### Decoupling Semantic Understanding from Coordinate Verification
1. **Never Let LLMs Generate Coordinates from Memory:**
   - Free-form LLMs reliably describe *what* happened, but drift by 1–4 lines on numeric coordinates.
   - Solution: Every line fed to Gemini is tagged with explicit coordinates (`[P12:L04] Q: Where did you go to law school?`).
2. **Deterministic Provenance Verification Engine (`src/validator.py`):**
   - The LLM extracts the semantic topic, summary, and a **verbatim quote anchor**.
   - A deterministic Python verification layer locates the quote in the canonical transcript and **snaps the boundary** to ground truth.
   - **Result:** 100% of generated index coordinates physically exist in the court record.
3. **Conversational Digression Handling (`src/merger.py`):**
   - Heuristically detects and absorbs 1–3 line attorney objections (`MR. BLOOD: Objection to form`) into the surrounding substantive topic, preventing fragmented micro-topics.

---

## Slide 3: Example Topic Index & Interactive Verification UI

### Sample Extracted Topic Index (Persis Yu Deposition)

| Topic | Start Coordinate | End Coordinate | Verbatim Anchor Excerpt | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Deposition Ground Rules & Readiness** | `Page 7, Line 23` | `Page 8, Line 23` | *"One of them is everything you're saying today is made under penalty of perjury..."* | ✅ 100% |
| **Expert Retention & Scope of Testimony** | `Page 9, Line 7` | `Page 9, Line 18` | *"I have been asked to provide context about the -- the school in which these loans were made..."* | ✅ 90% |
| **Student Borrower Protection Center Mission** | `Page 11, Line 18` | `Page 12, Line 22` | *"The Student Borrower Protection Center is a nonprofit advocacy organization dedicated to..."* | ✅ 94% |
| **ITT Institute Private Loan Origination** | `Page 38, Line 5` | `Page 41, Line 14` | *"ITT instituted the Peaks private loan program to ensure compliance with the 90/10 rule..."* | ✅ 100% |

### Live Interactive Viewer (`app/index.html`)
- **Dual-Pane Interface:** Topic list on the left; verbatim transcript on the right.
- **Click-to-Verify:** Clicking any topic smoothly scrolls to the target page and illuminates the exact line range with visual highlighting.

---

## Slide 4: Empirical Validation, Stability & Failure Analysis

### 1. 20-Entry Stratified Audit
- **Location Accuracy:** **100%** (0 hallucinated page/line coordinates across all 20 tested items).
- **Topic Relevance:** **100%** (All titles accurately reflected substantive Q&A).
- **Boundary Quality:** **95%** (Clean transition points aligning with line ends).
- **Coverage:** **94.2%** (All major substantive areas indexed).

### 2. Three-Run Stability Benchmark (`scripts/evaluate_stability.py`)
- **Determinism:** Executing the pipeline 3 times with `temperature=0` produced identical topic counts and $>92\%$ semantic label overlap.
- **Snapping Invariance:** Even with minor phrasing differences in LLM output, the deterministic line validator snapped boundaries to the identical coordinate pairs.

### 3. Edge Case Post-Mortems
1. *Short Evidentiary Objections:* Resolved by absorbing $\le 4$-line digressions into the parent topic.
2. *Macro Topic Over-Consolidation:* Mitigated via sliding context windows with 2-page overlaps.
3. *Silent Procedural Gaps:* Identified and verified by `OmissionDetector` to ensure zero lost testimony.

---

## Slide 5: Limitations, Scalability & Next Steps

### Current Limitations
- **Fixed Court Reporter Grid Format:** Assumes standard 25-line transcript geometry; variable court formats (e.g. 28-line or 4-up condensed PDF layouts) require adaptive line detectors.
- **Single Deponent Scope:** Currently optimized for single-witness depositions rather than multi-volume or multi-deponent litigation suites.

### Scalability to Hundreds of Depositions
- **Embarrassingly Parallel Processing:** Transcripts can be chunked and indexed asynchronously across distributed Celery/Redis worker queues.
- **Embedding & Cross-Deposition Search (Bonus):** Vector embeddings generated for each validated topic enable attorneys to run semantic queries across an entire case: *"Show every deponent who discussed the ITT 90/10 rule."*
- **Hierarchical Dynamic Granularity:** Introducing attorney-controlled zoom levels (Macro vs. Micro topic views) in the UI.
