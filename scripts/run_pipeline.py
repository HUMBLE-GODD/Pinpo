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
from typing import Optional
import argparse
from src.exporter import TopicIndexExporter
from src.models import TopicIndex, TopicEntry
from scripts.export_viewer_data import export_viewer_data

DEFAULT_PDF = "data/raw/deposition_persis_yu.pdf"


def run_pipeline(
    pdf_path: str = DEFAULT_PDF,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    witness: Optional[str] = None,
    case_name: Optional[str] = None,
    date: Optional[str] = None,
    max_pages: Optional[int] = None,
    chunk_size_pages: int = 12,
    overlap_pages: int = 2,
    output_dir: str = "data/output",
    update_viewer: bool = False
) -> TopicIndex:
    print("=" * 70)
    print("PINPO: AI-POWERED DEPOSITION TOPIC INDEXING PIPELINE")
    print("=" * 70)

    # 1. Deterministic Parsing & Auto-Detection
    parser = TranscriptParser(pdf_path)
    meta = parser.extract_metadata()

    # Resolve metadata with CLI overrides
    resolved_witness = witness or meta.get("witness", "Witness")
    resolved_case = case_name or meta.get("case_name", "Deposition Examination")
    resolved_date = date or meta.get("date", "Unknown Date")

    # Resolve page bounds
    if start_page is None or end_page is None:
        auto_start, auto_end = parser.auto_detect_bounds()
        resolved_start = start_page if start_page is not None else auto_start
        resolved_end = end_page if end_page is not None else auto_end
    else:
        resolved_start = start_page
        resolved_end = end_page

    # Apply max_pages ceiling if specified
    if max_pages and max_pages > 0:
        resolved_end = min(resolved_end, resolved_start + max_pages - 1)

    print(f"\n[1/6] Ingesting Transcript: {pdf_path}")
    print(f"      - Deponent:     {resolved_witness}")
    print(f"      - Matter:       {resolved_case}")
    print(f"      - Date:         {resolved_date}")
    print(f"      - Page Range:   Pages {resolved_start} to {resolved_end}")

    canonical_lines = parser.parse(
        start_page=resolved_start, 
        end_page=resolved_end,
        witness=resolved_witness
    )
    print(f"      -> Parsed {len(canonical_lines)} lines with canonical (page, line) coordinates.")

    if not canonical_lines:
        raise ValueError(f"No substantive testimony lines found in {pdf_path} between pages {resolved_start} and {resolved_end}.")

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
        title=f"Deposition of {resolved_witness} - Topic Index",
        witness=resolved_witness,
        date=resolved_date,
        case_name=resolved_case,
        total_pages=(resolved_end - resolved_start + 1),
        total_lines=len(canonical_lines),
        topics=final_topics,
        metadata={
            "pdf_source": str(pdf_path),
            "start_page": resolved_start,
            "end_page": resolved_end,
            "coverage_percentage": omission_report.coverage_percentage,
            "verified_topics": sum(1 for t in final_topics if t.verified),
            "uncovered_segments_count": len(omission_report.uncovered_segments)
        }
    )

    # Export formats
    exporter = TopicIndexExporter(output_dir)
    base_name = Path(pdf_path).stem + "_topic_index"
    exporter.export_all(topic_index, base_name=base_name)
    # Also export as standard topic_index.* for viewer compatibility
    exporter.export_all(topic_index, base_name="topic_index")

    print(f"\n[+] Successfully exported to {output_dir}:")
    print(f"    - JSON:     {output_dir}/{base_name}.json")
    print(f"    - Markdown: {output_dir}/{base_name}.md")
    print(f"    - HTML:     {output_dir}/{base_name}.html")

    # Update web viewer data if requested
    if update_viewer:
        print("\n[*] Updating interactive web viewer dataset...")
        export_viewer_data(
            pdf_path=pdf_path,
            start_page=resolved_start,
            end_page=resolved_end,
            topic_index_json=f"{output_dir}/topic_index.json"
        )

    return topic_index


def main():
    parser = argparse.ArgumentParser(
        description="Pinpo: AI-Powered Deposition Topic Index & Source Provenance Engine"
    )
    parser.add_argument(
        "--pdf", 
        type=str, 
        default=DEFAULT_PDF,
        help=f"Path to court reporter deposition PDF (default: {DEFAULT_PDF})"
    )
    parser.add_argument(
        "--start-page", 
        type=int, 
        default=None,
        help="Starting printed page of substantive testimony (auto-detected if omitted)"
    )
    parser.add_argument(
        "--end-page", 
        type=int, 
        default=None,
        help="Ending printed page of substantive testimony (auto-detected if omitted)"
    )
    parser.add_argument(
        "--witness", 
        type=str, 
        default=None,
        help="Deponent / Witness name (auto-extracted from title page if omitted)"
    )
    parser.add_argument(
        "--case", 
        type=str, 
        default=None,
        help="Matter / Case name (auto-extracted from title page if omitted)"
    )
    parser.add_argument(
        "--date", 
        type=str, 
        default=None,
        help="Deposition date (auto-extracted if omitted)"
    )
    parser.add_argument(
        "--max-pages", 
        type=int, 
        default=None,
        help="Limit processing to first N pages (ideal for fast test runs & quota saving)"
    )
    parser.add_argument(
        "--chunk-size", 
        type=int, 
        default=12,
        help="Sliding window context size in pages (default: 12)"
    )
    parser.add_argument(
        "--overlap", 
        type=int, 
        default=2,
        help="Context window overlap in pages (default: 2)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="data/output",
        help="Directory to save exported JSON, Markdown, and HTML reports"
    )
    parser.add_argument(
        "--update-viewer", 
        action="store_true",
        help="Automatically compile viewer data so web UI displays this deposition"
    )

    args = parser.parse_args()

    run_pipeline(
        pdf_path=args.pdf,
        start_page=args.start_page,
        end_page=args.end_page,
        witness=args.witness,
        case_name=args.case,
        date=args.date,
        max_pages=args.max_pages,
        chunk_size_pages=args.chunk_size,
        overlap_pages=args.overlap,
        output_dir=args.output_dir,
        update_viewer=args.update_viewer
    )


if __name__ == "__main__":
    main()
