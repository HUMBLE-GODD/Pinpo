"""
Baseline Topic Segmentation Runner.
Executes chunk-based LLM topic extraction without post-processing or deterministic validation,
generating the raw candidate index to establish a baseline.
"""

import sys
import json
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser import TranscriptParser
from src.chunker import TranscriptChunker
from src.segmenter import TopicSegmenter

DEFAULT_PDF = "data/raw/deposition_persis_yu.pdf"
OUTPUT_DIR = Path("data/output")


def run_baseline(
    pdf_path: str = DEFAULT_PDF,
    chunk_size_pages: int = 10,
    overlap_pages: int = 1,
    max_pages: int = 88
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_output_path = OUTPUT_DIR / "topic_index_raw.json"

    print(f"[*] Initializing Transcript Parser for: {pdf_path}")
    parser = TranscriptParser(pdf_path)
    lines = parser.parse(start_page=7, end_page=max_pages)
    print(f"[*] Successfully parsed {len(lines)} canonical lines across pages 7 to {max_pages}.")

    print(f"[*] Chunking transcript into {chunk_size_pages}-page windows (overlap: {overlap_pages})...")
    chunker = TranscriptChunker(chunk_size_pages=chunk_size_pages, overlap_pages=overlap_pages)
    chunks = chunker.create_chunks(lines)
    print(f"[*] Created {len(chunks)} contextual chunks.")

    segmenter = TopicSegmenter()
    all_raw_topics = []

    print(f"[*] Beginning baseline LLM topic extraction across {len(chunks)} chunks...")
    for idx, chunk in enumerate(chunks, 1):
        print(f"    -> Processing Chunk {idx}/{len(chunks)} (Pages {chunk.start_page} to {chunk.end_page})...")
        chunk_topics = segmenter.segment_chunk(chunk)
        print(f"       Extracted {len(chunk_topics)} candidate topics.")
        for t in chunk_topics:
            all_raw_topics.append(t.model_dump())
        time.sleep(1)  # Respect free tier rate limits

    print(f"\n[*] Total candidate topics extracted: {len(all_raw_topics)}")
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump(all_raw_topics, f, indent=2)

    print(f"[+] Baseline topic index saved to: {raw_output_path}")
    return all_raw_topics


if __name__ == "__main__":
    run_baseline()
