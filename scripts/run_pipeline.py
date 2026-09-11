"""
End-to-End DepoIndex Pipeline Runner.
Orchestrates Ingestion -> Chunking -> LLM Segmentation -> Provenance Validation ->
Boundary Merging -> Omission Audit -> Structured Export.
"""

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser import TranscriptParser
from src.chunker import TranscriptChunker
from src.segmenter import TopicSegmenter
from src.validator import ProvenanceValidator
from src.merger import TopicMerger
from src.omission_detector import OmissionDetector
from src.exporter import TopicIndexExporter
from src.models import TopicIndex, TopicEntry

DEFAULT_PDF = "data/raw/deposition_persis_yu.pdf"


def run_pipeline(
    pdf_path: str = DEFAULT_PDF,
    start_page: int = 7,
    end_page: int = 88,
    chunk_size_pages: int = 12,
    overlap_pages: int = 2
) -> TopicIndex:
    print("=" * 70)
    print("PINPO: AI-POWERED DEPOSITION TOPIC INDEXING PIPELINE")
    print("=" * 70)

    # 1. Deterministic Parsing
    print(f"\n[1/6] Ingesting Transcript: {pdf_path} (Pages {start_page}..{end_page})")
    parser = TranscriptParser(pdf_path)
    canonical_lines = parser.parse(start_page=start_page, end_page=end_page)
    print(f"      -> Parsed {len(canonical_lines)} lines with canonical (page, line) coordinates.")

    # 2. Window Chunking
    print(f"\n[2/6] Chunking Transcript into {chunk_size_pages}-page windows (overlap: {overlap_pages})...")
    chunker = TranscriptChunker(chunk_size_pages=chunk_size_pages, overlap_pages=overlap_pages)
    chunks = chunker.create_chunks(canonical_lines)
    print(f"      -> Generated {len(chunks)} contextual processing chunks.")

    # 3. LLM Extraction
    print(f"\n[3/6] Extracting Topics with Google Gemini (temperature=0)...")
    segmenter = TopicSegmenter()
    raw_topics = []

    for idx, chunk in enumerate(chunks, 1):
        print(f"      - Processing Chunk {idx}/{len(chunks)}: Pages {chunk.start_page} to {chunk.end_page}...")
        extracted = segmenter.segment_chunk(chunk)
        print(f"        Extracted {len(extracted)} candidate topics.")
        raw_topics.extend(extracted)
        time.sleep(1)

    print(f"      -> Total raw candidate topics: {len(raw_topics)}")

    # 4. Provenance Validation & Coordinate Snapping
    print(f"\n[4/6] Running Zero-Hallucination Provenance Validation Engine...")
    validator = ProvenanceValidator(parser)
    validated_topics = validator.validate_batch(raw_topics)
    verified_count = sum(1 for t in validated_topics if t.verified)
    print(f"      -> Mathematically verified {verified_count}/{len(validated_topics)} topics against transcript text.")

    # 5. Boundary Smoothing & Digression Absorption
    print(f"\n[5/6] Merging adjacent topics & filtering conversational digressions...")
    merger = TopicMerger(title_similarity_threshold=0.70)
    final_topics = merger.merge(validated_topics)
    print(f"      -> Consolidated into {len(final_topics)} high-level chronological topics.")

    # 6. Omission Audit
    print(f"\n[6/6] Auditing Line Coverage & Checking Silent Omissions...")
    detector = OmissionDetector(canonical_lines)
    omission_report = detector.audit(final_topics)
    print(f"      -> Total Transcript Lines: {omission_report.total_lines}")
    print(f"      -> Covered Lines:         {omission_report.covered_lines} ({omission_report.coverage_percentage}%)")
    print(f"      -> Critical Omissions:     {'None (Clean)' if not omission_report.has_critical_omissions else 'Detected'}")

    # Build Final TopicIndex
    topic_index = TopicIndex(
        title="Deposition of Persis Yu - Topic Index",
        witness="Persis Yu",
        date="March 28, 2023",
        case_name="Heather Turrey vs. Vervent, Inc.",
        total_pages=(end_page - start_page + 1),
        total_lines=len(canonical_lines),
        topics=final_topics,
        metadata={
            "coverage_percentage": omission_report.coverage_percentage,
            "verified_topics": sum(1 for t in final_topics if t.verified),
            "uncovered_segments_count": len(omission_report.uncovered_segments)
        }
    )

    # Export formats
    exporter = TopicIndexExporter("data/output")
    exporter.export_all(topic_index, base_name="topic_index")
    print(f"\n[+] Successfully exported:")
    print(f"    - JSON:     data/output/topic_index.json")
    print(f"    - Markdown: data/output/topic_index.md")
    print(f"    - HTML:     data/output/topic_index.html")

    return topic_index


if __name__ == "__main__":
    run_pipeline()
