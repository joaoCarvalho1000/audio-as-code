"""Fail when the checked-in schema differs from the installed score model."""

import json
from pathlib import Path

from audio_as_code import Song

path = Path(__file__).resolve().parents[2] / "schemas/song-v1.schema.json"
if json.loads(path.read_text(encoding="utf-8")) != Song.model_json_schema():
    raise SystemExit("Schema drift: run uv run aac schema -o schemas/song-v1.schema.json")
print("The checked-in score schema matches Song.model_json_schema().")
