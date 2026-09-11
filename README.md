# Pinpo: AI-Powered Deposition Topic Index & Verification Engine

**Pinpo** is an AI-powered legal document intelligence system that converts raw deposition transcripts into a verifiable, chronologically ordered **Topic Index** while preserving **100% line-level source provenance**.

Built for litigation attorneys who need to navigate 100–300+ pages of spoken witness testimony rapidly without the risk of hallucinated references.

---

## Engineering Features

- **Deterministic Coordinate Ingestion:** Direct parsing of court reporter standard 25-line grids `(page, line, speaker, text, timestamp)`.
- **Zero-Line-Drop Guarantee:** Strict continuous line tracking across substantive examination pages.
- **Provenance-First Architecture:** Eliminates hallucination by separating semantic topic recognition from coordinate verification.
- **Deterministic Validation:** Mathematical text and coordinate verification against original testimony.

---

## Quickstart

### 1. Prerequisites
- Python 3.10+
- Recommended: Google Gemini API key (free tier supported)

### 2. Setup
```bash
git clone https://github.com/HUMBLE-GODD/Pinpo.git
cd Pinpo
pip install -r requirements.txt
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

### 3. Run Verification Tests
```bash
pytest tests/test_parser.py
```
