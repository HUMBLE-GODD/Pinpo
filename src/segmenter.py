"""
LLM-Powered Semantic Topic Segmenter.
Communicates with Google Gemini API using structured JSON output and temperature=0
to identify legal topics, summaries, and verbatim quote anchors across transcript chunks.

This is Stage 4 of the Pinpo pipeline. Takes cleaned chunks from the cleaner and
sends them to the Gemini LLM with metadata context to extract structured topic entries.

INTERVIEWER CRITICISM #2 ADDRESSED HERE:
  "You are not using metadata in the LLM."
  → This module injects deposition metadata (witness, case, attorney, date)
    into the LLM prompt as a "DEPOSITION CONTEXT" block.
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv  # Loads API key from .env file

from src.models import TopicEntry
from src.chunker import TranscriptChunk

load_dotenv()  # Load GEMINI_API_KEY from .env into os.environ


class TopicSegmenter:
    """
    Extracts structured topic candidates from transcript chunks via Gemini LLM.
    Enforces deterministic output via zero-temperature and strict JSON schemas.
    """

    # =========================================================================
    # [BLOCK-14: System Prompt — LLM Instructions for Topic Extraction]
    # WHAT: The system-level instructions that tell Gemini HOW to analyze
    #       deposition testimony and WHAT structured output to produce.
    # WHY: A precise system prompt is critical to get consistent, structured
    #      JSON output. Without it, the LLM would produce free-form text.
    # KEY INSTRUCTIONS TO THE LLM:
    #   1. Extract topic, start_page, start_line, end_page, end_line, summary, supporting_quote
    #   2. "Strictly observe the line coordinates in [P07:L12] tags"
    #   3. "Group related Q&A into coherent topics" (don't fragment)
    #   4. "Absorb brief 1-3 line attorney objections" (don't create separate objection topics)
    #   5. "Return ONLY a valid JSON array" (no markdown, no commentary)
    # DESIGN: temperature=0.0 ensures deterministic, reproducible output
    # =========================================================================
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

    # =========================================================================
    # [BLOCK-15: Multi-Model Fallback Cascade]
    # WHAT: A list of Gemini model names to try in sequence if the primary model
    #       fails (rate-limited, unavailable, or quota exceeded).
    # WHY: Gemini has per-model quotas. If gemini-3.5-flash hits its rate limit
    #       (HTTP 429), the segmenter automatically tries gemini-3.5-flash-lite,
    #       then gemini-flash-lite-latest, etc. This prevents pipeline failure
    #       due to temporary quota exhaustion.
    # HOW: models_to_try = [primary_model] + [fallbacks not equal to primary]
    #      Each model gets max_retries attempts before moving to the next.
    # =========================================================================
    FALLBACK_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3-flash-preview",
    ]

    # =========================================================================
    # [BLOCK-16: Segmenter Initialization — API Key, Model, Metadata]
    # WHAT: Initializes the segmenter with:
    #   - api_key: Gemini API key (from .env or parameter)
    #   - model: Primary Gemini model name
    #   - max_retries: Retry count per model (default: 3)
    #   - metadata: Deposition context dict (witness, case_name, attorney, date)
    # WHY metadata: This is the key design response to interviewer criticism #2.
    #   The metadata dict is injected into every LLM prompt so Gemini knows WHO
    #   the witness is, WHAT case this is, and WHEN the deposition occurred.
    #   This context reduces hallucination because the LLM has domain grounding.
    # =========================================================================
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, str]] = None
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")  # Load from .env if not provided
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")  # Default model
        self.max_retries = max_retries  # Retry attempts per model before fallback
        self.metadata = metadata or {}  # Deposition context for prompt injection

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize TopicSegmenter.")

    # =========================================================================
    # [BLOCK-17: segment_chunk() — Core LLM Extraction with Metadata Injection]
    # WHAT: Takes a single TranscriptChunk and sends it to Gemini to extract topics.
    # HOW IT WORKS:
    #   1. Build DEPOSITION CONTEXT block from metadata dict
    #   2. Combine system prompt + metadata + chunk text into one LLM prompt
    #   3. Send POST request to Gemini API with temperature=0.0
    #   4. Parse JSON response → create TopicEntry objects
    #   5. If primary model fails → try fallback models in cascade
    # METADATA INJECTION (addresses interviewer criticism #2):
    #   The metadata block looks like:
    #     DEPOSITION CONTEXT:
    #       Witness/Deponent: Persis Yu
    #       Case/Matter: Heather Turrey vs. Vervent, Inc.
    #       Examining Attorney: Mr. Purcell
    #       Date: March 28, 2023
    #   This is prepended to the user prompt so Gemini has domain context.
    # API DETAILS:
    #   - Endpoint: generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    #   - temperature=0.0 → deterministic output (same input = same output)
    #   - responseMimeType="application/json" → forces structured JSON response
    #   - timeout=45 seconds per request
    # ERROR HANDLING:
    #   - HTTP 429 (rate limit) → try next model in cascade
    #   - HTTP 404 (model not found) → try next model
    #   - Other errors → retry with exponential backoff (2s, 4s, 8s)
    # =========================================================================
    def segment_chunk(self, chunk: TranscriptChunk) -> List[TopicEntry]:
        """Processes a single transcript chunk and returns candidate topic entries."""

        # --- Build metadata context block for domain-aware topic extraction ---
        # This is the DEPOSITION CONTEXT that addresses interviewer criticism #2
        meta_context = ""
        if self.metadata:
            meta_lines = ["DEPOSITION CONTEXT:"]
            if self.metadata.get("witness"):
                meta_lines.append(f"  Witness/Deponent: {self.metadata['witness']}")
            if self.metadata.get("case_name"):
                meta_lines.append(f"  Case/Matter: {self.metadata['case_name']}")
            if self.metadata.get("attorney"):
                meta_lines.append(f"  Examining Attorney: {self.metadata['attorney']}")
            if self.metadata.get("date"):
                meta_lines.append(f"  Date: {self.metadata['date']}")
            meta_context = "\n".join(meta_lines) + "\n\n"

        # --- Construct the user prompt ---
        # Format: [METADATA CONTEXT] + "Analyze this segment" + [CHUNK TEXT]
        user_prompt = f"""{meta_context}Analyze this deposition transcript segment (Pages {chunk.start_page} to {chunk.end_page}):

{chunk.formatted_text}

Extract all chronological topic segments according to the specified JSON schema."""

        # --- Build the Gemini API request payload ---
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,  # Deterministic — no randomness in output
                "topP": 0.95,  # Nucleus sampling threshold
                "responseMimeType": "application/json"  # Force structured JSON response
            }
        }

        # --- Multi-model fallback cascade ---
        # Try primary model first, then fallbacks if it fails
        models_to_try = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]

        for current_model in models_to_try:
            # Construct the API endpoint URL with the model name and API key
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={self.api_key}"

            for attempt in range(1, self.max_retries + 1):
                try:
                    # Send HTTP POST request to Gemini API
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )

                    with urllib.request.urlopen(req, timeout=45) as response:
                        raw_resp = json.loads(response.read().decode("utf-8"))
                        candidates = raw_resp.get("candidates", [])
                        if not candidates:
                            return []  # No candidates = empty response

                        # Extract the text content from the response
                        content_text = candidates[0]["content"]["parts"][0]["text"].strip()

                        # Clean any leading/trailing markdown code fences if present
                        # Sometimes Gemini wraps JSON in ```json ... ``` despite our instructions
                        if content_text.startswith("```json"):
                            content_text = content_text[7:]
                        if content_text.startswith("```"):
                            content_text = content_text[3:]
                        if content_text.endswith("```"):
                            content_text = content_text[:-3]

                        # Parse the JSON response into a list of topic dictionaries
                        parsed_json = json.loads(content_text.strip())
                        entries: List[TopicEntry] = []

                        # Convert each JSON object into a TopicEntry model
                        for item in parsed_json:
                            entry = TopicEntry(
                                topic=item.get("topic", "Untitled Topic").strip(),
                                start_page=int(item.get("start_page", chunk.start_page)),
                                start_line=int(item.get("start_line", 1)),
                                end_page=int(item.get("end_page", chunk.end_page)),
                                end_line=int(item.get("end_line", 25)),
                                summary=item.get("summary", "").strip(),
                                supporting_quote=item.get("supporting_quote", "").strip(),
                                confidence=0.85,  # Baseline unverified LLM candidate confidence
                                verified=False  # Will be set by validator (BLOCK-18)
                            )
                            entries.append(entry)

                        # Remember which model succeeded for future chunks
                        self.model = current_model
                        return entries

                except urllib.error.HTTPError as http_err:
                    err_body = http_err.read().decode("utf-8", errors="replace")
                    if http_err.code in (429, 404):
                        # 429 = rate limited, 404 = model not found → try next model
                        print(f"[*] Model {current_model} returned HTTP {http_err.code} (quota/availability). Trying fallback model...")
                        break  # Break attempt loop → try next model in cascade
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                        continue
                    raise RuntimeError(f"Gemini API request failed with HTTP {http_err.code}: {err_body}") from http_err
                except Exception as e:
                    if attempt < self.max_retries:
                        time.sleep(2)  # Simple retry delay
                        continue
                    print(f"[!] Error with model {current_model}: {e}. Trying fallback...")
                    break  # Try next model

        return []  # All models exhausted — return empty
