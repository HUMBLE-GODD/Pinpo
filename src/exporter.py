"""
Topic Index Exporter.
Produces standard machine-readable JSON and human-readable HTML/Markdown formats.
"""

import html
import json
from pathlib import Path
from typing import Optional
from src.models import TopicIndex


class TopicIndexExporter:
    """Exports structured TopicIndex into JSON, Markdown, and self-contained HTML."""

    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, index: TopicIndex, base_name: str = "topic_index"):
        """Exports JSON, Markdown, and HTML formats simultaneously."""
        self.export_json(index, self.output_dir / f"{base_name}.json")
        self.export_markdown(index, self.output_dir / f"{base_name}.md")
        self.export_html(index, self.output_dir / f"{base_name}.html")

    def export_json(self, index: TopicIndex, file_path: Path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(index.model_dump(), f, indent=2)

    def export_markdown(self, index: TopicIndex, file_path: Path):
        md_lines = [
            f"# {index.title}",
            f"**Deponent / Witness:** {index.witness}  ",
            f"**Date:** {index.date or 'March 28, 2023'}  ",
            f"**Total Substantive Pages:** {index.total_pages} (Total Lines: {index.total_lines})  ",
            f"**Total Topics Identified:** {len(index.topics)}  ",
            "",
            "---",
            "",
            "| # | Topic | Start Coordinate | End Coordinate | Summary | Supporting Quote | Verified |",
            "|---|---|---|---|---|---|:---:|",
        ]

        for idx, t in enumerate(index.topics, 1):
            ver_tag = "✅" if t.verified else "⚠️"
            quote_clean = t.supporting_quote.replace("\n", " ").replace("|", "\\|")
            summary_clean = t.summary.replace("\n", " ").replace("|", "\\|")
            quote_display = f'*"{quote_clean[:100]}..."*' if quote_clean else "*(No quote)*"
            md_lines.append(
                f"| {idx} | **{t.topic}** | {t.start_coordinate} | {t.end_coordinate} | {summary_clean} | {quote_display} | {ver_tag} |"
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

    def export_html(self, index: TopicIndex, file_path: Path):
        rows = []
        for idx, t in enumerate(index.topics, 1):
            badge_class = "badge-verified" if t.verified else "badge-unverified"
            badge_text = "Verified" if t.verified else "Review"
            safe_topic = html.escape(t.topic)
            safe_summary = html.escape(t.summary)
            safe_quote = html.escape(t.supporting_quote)
            rows.append(f"""
            <tr>
                <td class="num">{idx}</td>
                <td class="topic-name"><strong>{safe_topic}</strong></td>
                <td class="coord">{t.start_coordinate}</td>
                <td class="coord">{t.end_coordinate}</td>
                <td class="summary">{safe_summary}</td>
                <td class="quote">&ldquo;{safe_quote}&rdquo;</td>
                <td><span class="badge {badge_class}">{badge_text} ({int(t.confidence*100)}%)</span></td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{index.title} - Pinpo</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 32px;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
            background: #ffffff;
            padding: 32px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }}
        header {{
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        h1 {{
            margin: 0 0 8px 0;
            font-size: 26px;
            color: #1e293b;
        }}
        .meta-bar {{
            display: flex;
            gap: 24px;
            font-size: 14px;
            color: #64748b;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 16px;
        }}
        th {{
            background: #f1f5f9;
            text-align: left;
            padding: 12px 14px;
            font-weight: 600;
            color: #475569;
            border-bottom: 2px solid #cbd5e1;
        }}
        td {{
            padding: 14px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        tr:hover td {{
            background-color: #f8fafc;
        }}
        .num {{ color: #94a3b8; font-weight: bold; width: 30px; }}
        .topic-name {{ color: #0284c7; width: 220px; }}
        .coord {{ font-family: monospace; font-weight: 600; color: #334155; width: 140px; white-space: nowrap; }}
        .summary {{ color: #334155; line-height: 1.5; }}
        .quote {{ color: #64748b; font-style: italic; font-size: 13px; line-height: 1.4; }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-verified {{ background: #dcfce7; color: #166534; }}
        .badge-unverified {{ background: #fef3c7; color: #92400e; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{index.title}</h1>
            <div class="meta-bar">
                <div><strong>Witness:</strong> {index.witness}</div>
                <div><strong>Date:</strong> {index.date or 'March 28, 2023'}</div>
                <div><strong>Pages:</strong> {index.total_pages} (Lines: {index.total_lines})</div>
                <div><strong>Topics:</strong> {len(index.topics)}</div>
            </div>
        </header>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Topic</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Summary</th>
                    <th>Supporting Quote</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
