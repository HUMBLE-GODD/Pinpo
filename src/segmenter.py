"""
LLM-Powered Semantic Topic Segmenter.
Communicates with Google Gemini API using structured JSON output and temperature=0
to identify legal topics, summaries, and verbatim quote anchors across transcript chunks.
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from src.models import TopicEntry
from src.chunker import TranscriptChunk

load_dotenv()


class TopicSegmenter:
    """
    Extracts structured topic candidates from transcript chunks via Gemini LLM.
    Enforces deterministic output via zero-temperature and strict JSON schemas.
    """

    SYSTEM_PROMPT = """You are an elite legal technology engineer and litigation assistant.
Your task is to analyze legal deposition testimony and segment it into coherent, chronologically ordered topic chapters.

For each distinct topic, extract:
1. topic: A concise, professional legal topic title (e.g., 'Educational Background & Degrees', 'ITT Institute Loan Practices', 'Department of Education Inquiries', 'Ground Rules & Admonitions').
2. start_page: Integer printed page where the topic discussion begins.
3. start_line: Integer line (1..25) where the topic discussion begins.
4. end_page: Integer printed page where the topic discussion ends.
5. end_line: Integer line (1..25) where the topic discussion ends.
6. summary: 1-2 factual sentences summarizing what was asked and answered.
7. supporting_quote: An exact verbatim quote from the testimony that anchors this topic.

Rules:
- Strictly observe the line coordinates provided in tags like [P07:L12].
- Group related Q&A into coherent topics rather than fragmenting each individual question.
- Absorb brief 1-3 line attorney objections into the primary active topic.
- Return ONLY a valid JSON array of objects adhering to this schema. No markdown backticks or commentary."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize TopicSegmenter.")

    def segment_chunk(self, chunk: TranscriptChunk) -> List[TopicEntry]:
        """Processes a single transcript chunk and returns candidate topic entries."""
        user_prompt = f"""Analyze this deposition transcript segment (Pages {chunk.start_page} to {chunk.end_page}):

{chunk.formatted_text}

Extract all chronological topic segments according to the specified JSON schema."""

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "topP": 0.95,
                "responseMimeType": "application/json"
            }
        }

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )

                with urllib.request.urlopen(req, timeout=45) as response:
                    raw_resp = json.loads(response.read().decode("utf-8"))
                    candidates = raw_resp.get("candidates", [])
                    if not candidates:
                        return []

                    content_text = candidates[0]["content"]["parts"][0]["text"].strip()
                    # Clean any leading/trailing markdown code fences if present
                    if content_text.startswith("```json"):
                        content_text = content_text[7:]
                    if content_text.startswith("```"):
                        content_text = content_text[3:]
                    if content_text.endswith("```"):
                        content_text = content_text[:-3]

                    parsed_json = json.loads(content_text.strip())
                    entries: List[TopicEntry] = []

                    for item in parsed_json:
                        # Validate mandatory fields
                        entry = TopicEntry(
                            topic=item.get("topic", "Untitled Topic").strip(),
                            start_page=int(item.get("start_page", chunk.start_page)),
                            start_line=int(item.get("start_line", 1)),
                            end_page=int(item.get("end_page", chunk.end_page)),
                            end_line=int(item.get("end_line", 25)),
                            summary=item.get("summary", "").strip(),
                            supporting_quote=item.get("supporting_quote", "").strip(),
                            confidence=0.85,  # Baseline unverified LLM candidate confidence
                            verified=False
                        )
                        entries.append(entry)

                    return entries

            except urllib.error.HTTPError as http_err:
                if http_err.code == 429 and attempt < self.max_retries:
                    wait_sec = 2 ** attempt
                    time.sleep(wait_sec)
                    continue
                raise RuntimeError(f"Gemini API request failed with HTTP {http_err.code}: {http_err.read().decode('utf-8')}") from http_err
            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(2)
                    continue
                raise RuntimeError(f"Failed to segment chunk {chunk.chunk_id}: {str(e)}") from e

        return []
