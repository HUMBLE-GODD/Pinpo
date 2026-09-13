"""
Compiles canonical transcript lines and generated TopicIndex into app/viewer_data.js
for zero-dependency standalone in-browser attorney verification.
"""

import sys
import json
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser import TranscriptParser

from typing import Optional
import argparse

DEFAULT_PDF = "data/raw/deposition_persis_yu.pdf"
TOPIC_INDEX_JSON = "data/output/topic_index.json"
APP_DIR = Path("app")


def export_viewer_data(
    pdf_path: str = DEFAULT_PDF,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    topic_index_json: str = TOPIC_INDEX_JSON,
    app_dir: str = "app"
):
    target_app_dir = Path(app_dir)
    target_app_dir.mkdir(parents=True, exist_ok=True)
    
    # Ingest transcript lines
    parser = TranscriptParser(pdf_path)
    meta = parser.extract_metadata()

    if start_page is None or end_page is None:
        auto_start, auto_end = parser.auto_detect_bounds()
        resolved_start = start_page if start_page is not None else auto_start
        resolved_end = end_page if end_page is not None else auto_end
    else:
        resolved_start = start_page
        resolved_end = end_page

    lines = parser.parse(start_page=resolved_start, end_page=resolved_end)
    serialized_lines = [
        {
            "global_id": l.global_line_id,
            "page": l.page,
            "line": l.line,
            "speaker": l.speaker,
            "text": l.text,
            "timestamp": l.timestamp
        }
        for l in lines
    ]

    # Load topic index if available, else load placeholder/raw
    topics = []
    title = f"Deposition of {meta.get('witness', 'Witness')}"
    witness = meta.get('witness', 'Witness')
    case_name = meta.get('case_name', 'Deposition Examination')
    date = meta.get('date', 'Unknown Date')

    if Path(topic_index_json).exists():
        with open(topic_index_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            topics = data.get("topics", [])
            title = data.get("title", title)
            witness = data.get("witness", witness)
            case_name = data.get("case_name", case_name)
            date = data.get("date", date)
    elif Path("data/output/topic_index_raw.json").exists():
        with open("data/output/topic_index_raw.json", "r", encoding="utf-8") as f:
            topics = json.load(f)

    js_content = f"""// Auto-generated deposition viewer data
window.DEPOSITION_DATA = {{
    title: {json.dumps(title)},
    witness: {json.dumps(witness)},
    date: {json.dumps(date)},
    caseName: {json.dumps(case_name)},
    topics: {json.dumps(topics, indent=2)},
    lines: {json.dumps(serialized_lines)}
}};
"""
    output_path = target_app_dir / "viewer_data.js"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"[+] Exported viewer dataset to: {output_path} ({len(serialized_lines)} lines, {len(topics)} topics)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export transcript lines & topic index to viewer dataset")
    parser.add_argument("--pdf", type=str, default=DEFAULT_PDF, help="PDF transcript path")
    parser.add_argument("--start-page", type=int, default=None, help="Start printed page")
    parser.add_argument("--end-page", type=int, default=None, help="End printed page")
    parser.add_argument("--json", type=str, default=TOPIC_INDEX_JSON, help="Topic Index JSON path")
    parser.add_argument("--app-dir", type=str, default="app", help="Output app directory")

    args = parser.parse_args()
    export_viewer_data(
        pdf_path=args.pdf,
        start_page=args.start_page,
        end_page=args.end_page,
        topic_index_json=args.json,
        app_dir=args.app_dir
    )
