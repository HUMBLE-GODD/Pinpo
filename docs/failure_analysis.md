# Failure Analysis & Edge Case Post-Mortems

Per docu3C technical requirements, this document analyzes **three challenging or failed edge cases** encountered during the semantic topic indexing of the *Deposition of Persis Yu*, detailing root causes and architectural remedies.

---

## Failure Case 1: Micro-Fragment Splintering from Attorney Objections

### 1. What did the system produce?
In raw extraction, when opposing counsel raised a standard evidentiary objection:
> *Page 12, Line 19 — MR. BLOOD: Objection; calls for legal conclusion.*  
> *Page 12, Line 21 — THE WITNESS: As I was saying...*

The baseline LLM produced a discrete, standalone topic entry:
* **Topic:** `Attorney Objection to Form`
* **Coordinate:** `Page 12, Line 19` to `Page 12, Line 20` (Span: 2 lines)
* **Confidence:** 0.85

### 2. What should it have produced?
The ongoing substantive topic—`"Department of Education Student Loan Servicing Proposals"`—should have seamlessly continued from `Page 11, Line 18` through `Page 12, Line 25`, absorbing the brief objection without splintering into micro-fragments.

### 3. Why did it fail?
LLMs are conditioned to detect dramatic tonal and speaker shifts. When the model encounters keywords like *"Objection"*, *"Lack of foundation"*, or *"Move to strike"*, it interprets the exchange as an adversarial shift in topic rather than a conversational interruption.

### 4. How was it improved?
We engineered a deterministic **Digression Filter** in `src/merger.py`:
- Any candidate topic spanning $\le 4$ lines that contains legal objection keywords (`OBJECTION`, `RECESS`, `OFF THE RECORD`) is automatically absorbed into the preceding substantive parent topic.
- The parent topic's `end_page` and `end_line` are expanded to cover the objection lines, preserving continuous topic flow.

---

## Failure Case 2: Over-Consolidation across Multi-Page Discussion

### 1. What did the system produce?
Across Pages 38 through 44, the witness testified extensively regarding ITT Educational Services' loan origination, tuition inflation, and state regulatory findings.
The system produced a single monolithic block:
* **Topic:** `ITT Educational Services Practices and Context`
* **Coordinate:** `Page 38, Line 1` to `Page 44, Line 18` (Span: 6 pages, 143 lines)

### 2. What should it have produced?
A litigation attorney preparing for trial needs finer granularity to pinpoint specific evidentiary points. The discussion should ideally have been segmented into three distinct sub-topics:
1. `ITT Tuition Cost Structure & PEAKS Private Loans` (Pages 38–40)
2. `State Attorney General Investigations & Enforcement` (Pages 41–42)
3. `Department of Education Program Reviews` (Pages 43–44)

### 3. Why did it fail?
The 12-page chunking window gave the LLM broad holistic context. Rather than tracking fine-grained question-level shifts, the model abstracted the entire 6-page section under a single macro-theme.

### 4. How would you improve it?
- **Hierarchical Two-Pass Segmentation:** 
  1. *Pass 1 (Macro):* Identifies high-level themes across the full document.
  2. *Pass 2 (Micro):* Evaluates any topic spanning $>100$ lines with a sliding 3-page window to identify internal inflection points and sub-topics.
- **Granularity Controls:** Add an attorney-configurable parameter in the UI (`granularity: "high" | "medium" | "low"`) that dynamically adjusts the segmentation threshold.

---

## Failure Case 3: Silent Gaps in Procedural Transitions (Unassigned Lines)

### 1. What did the system produce?
Between Page 28, Line 22 (where the attorney finished asking about a policy memo) and Page 29, Line 5 (where questioning on a new exhibit commenced), the transcript contained 8 lines of procedural dialogue:
> *Page 28, Line 23 — MR. PURCELL: Let's mark this as Exhibit 2.*  
> *Page 28, Line 24 — (Whereupon, Exhibit 2 was marked for identification.)*  
> *Page 29, Line 1 — MR. PURCELL: Showing you what has been marked...*

The baseline extraction ended Topic 18 at `P28:L22` and started Topic 19 at `P29:L05`, leaving 8 lines completely unassigned.

### 2. What should it have produced?
Either:
- An explicit procedural marker: `Marking & Introduction of Exhibit 2` (`P28:L23` to `P29:L04`); or
- Boundary snapping extending Topic 19 to begin at `P28:L23` to maintain 100% line coverage.

### 3. Why did it fail?
The LLM was instructed to extract *meaningful legal testimony*. Because exhibit markings and reporter parentheticals do not constitute sworn witness testimony, the LLM discarded them, creating unindexed voids.

### 4. How was it improved?
- We created `src/omission_detector.py` to audit line indices across the entire transcript.
- When an unassigned gap is detected, the detector checks whether the lines contain procedural keywords (`"EXHIBIT"`, `"RECESS"`, `"WHEREUPON"`).
- If procedural, the gap is classified as `is_administrative = True` (benign). If substantive speech is unassigned, it alerts the system and expands the neighboring topic boundary to prevent silent omission.
