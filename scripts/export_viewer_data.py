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

DEFAULT_PDF = "data/raw/deposition_persis_yu.pdf"
TOPIC_INDEX_JSON = "data/output/topic_index.json"
APP_DIR = Path("app")


def export_viewer_data():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ingest transcript lines
    parser = TranscriptParser(DEFAULT_PDF)
    lines = parser.parse(start_page=7, end_page=88)
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
    if Path(TOPIC_INDEX_JSON).exists():
        with open(TOPIC_INDEX_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            topics = data.get("topics", [])
    elif Path("data/output/topic_index_raw.json").exists():
        with open("data/output/topic_index_raw.json", "r", encoding="utf-8") as f:
            topics = json.load(f)

    js_content = f"""// Auto-generated deposition viewer data
window.DEPOSITION_DATA = {{
    title: "Deposition of Persis Yu",
    witness: "Persis Yu",
    date: "March 28, 2023",
    caseName: "Heather Turrey vs. Vervent, Inc.",
    topics: {json.dumps(topics, indent=2)},
    lines: {json.dumps(serialized_lines)}
}};
"""
    output_path = APP_DIR / "viewer_data.js"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"[+] Exported viewer dataset to: {output_path} ({len(serialized_lines)} lines, {len(topics)} topics)")


if __name__ == "__main__":
    export_viewer_data()
