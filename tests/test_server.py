"""
Unit tests for Pinpo Full-Stack Server & Upload API.
"""

import io
import json
import pytest
from pathlib import Path
from server import PinpoHandler, UPLOADS_DIR

SAMPLE_PDF = "data/raw/deposition_persis_yu.pdf"


def test_uploads_dir_exists():
    assert UPLOADS_DIR.exists()
    assert UPLOADS_DIR.is_dir()


def test_server_content_types():
    from server import CONTENT_TYPES
    assert ".html" in CONTENT_TYPES
    assert ".js" in CONTENT_TYPES
    assert ".css" in CONTENT_TYPES
    assert ".json" in CONTENT_TYPES
    assert ".pdf" in CONTENT_TYPES


def test_upload_sanitization():
    # Test safe filename generation
    dirty_name = "test/..\\deposition;persis#1.pdf"
    safe_name = "".join(c for c in dirty_name if c.isalnum() or c in "._- ")
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert safe_name.endswith(".pdf")
