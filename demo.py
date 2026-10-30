"""Try the app with a fictional persona (Maja Lindqvist) instead of your own documents.

    uv run python demo.py            real Claude calls via your .env credentials
    uv run python demo.py --offline  canned stand-in for the model, no AWS needed

Uses a separate data folder (demo-data), so your real material is never touched, and serves
samples/jobs on http://127.0.0.1:8001 so you can test "Fetch text" with a link.
"""

import argparse
import functools
import http.server
import os
import threading
from pathlib import Path

ROOT = Path(__file__).parent
PERSONA_DIR = ROOT / "samples" / "maja-lindqvist"
NOTE_FILE = ROOT / "samples" / "note-saker-som-inte-star-i-cv.txt"
JOBS_DIR = ROOT / "samples" / "jobs"
JOBS_PORT = 8001


def seed() -> int:
    """Load the persona's documents and note into the current data folder. Returns how many were added."""
    from app import ingest

    added = 0
    for path in sorted(PERSONA_DIR.iterdir()):
        ingest.add_source(path.name, "file", ingest.extract_text(path.name, path.read_bytes()))
        added += 1
    ingest.add_source("Saker som inte står i mitt CV", "note", NOTE_FILE.read_text(encoding="utf-8").strip())
    return added + 1


def serve_jobs() -> http.server.ThreadingHTTPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(JOBS_DIR))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", JOBS_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    os.environ["CV_DATA_DIR"] = str(ROOT / "demo-data")
    os.environ["CV_DEMO"] = "1"

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="use a canned stand-in for the model (no AWS)")
    if parser.parse_args().offline:
        os.environ["CV_FAKE_LLM"] = "1"

    import uvicorn

    from app import ingest
    from app.config import fake_llm_enabled, has_aws_credentials

    if not fake_llm_enabled() and not has_aws_credentials():
        raise SystemExit("No AWS credentials in .env. Add them, or run: uv run python demo.py --offline")

    if not ingest.list_sources():
        print(f"Seeded {seed()} sources for Maja Lindqvist.")
    serve_jobs()
    print(f"Model: {'canned offline stand-in' if fake_llm_enabled() else 'real Bedrock calls'}")
    print(f"Sample job pages: http://127.0.0.1:{JOBS_PORT}/kulturproducent.html and /js-only.html")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
