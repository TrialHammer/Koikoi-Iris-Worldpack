#!/usr/bin/env python3
"""Print a new Minecraft preview seed, excluding 1337 and recorded test seeds."""

import json
from pathlib import Path
import secrets

pack = Path(__file__).resolve().parents[1]
used = {1337}
for path in (pack / "docs/validation").glob("seed-*.json"):
    report = json.loads(path.read_text())
    used.add(report["seed"])
history = pack / "docs/validation/test-history.json"
if history.exists():
    used.update(entry["worldSeed"] for entry in json.loads(history.read_text()))
while True:
    candidate = secrets.randbits(62)
    if candidate and candidate not in used:
        print(candidate)
        break
