"""Kiểm chứng HTTP với model thật trong image, không dùng provider giả."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    token = os.environ["SUPPORTFLOW_AI_SERVICE_TOKEN"]
    deadline = time.monotonic() + 120
    while True:
        try:
            urllib.request.urlopen(args.url + "/health/embedding", timeout=3).close()
            break
        except (OSError, urllib.error.HTTPError):
            if time.monotonic() >= deadline:
                raise RuntimeError("embedding readiness timeout") from None
            time.sleep(1)
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "contracts/ai/knowledge-index/v1/fixtures.json").read_text(
        encoding="utf-8",
    ))
    payload = fixture["request"]
    payload["content"] += "\n\n## Kiểm tra dài\n\n" + "Kết nối VPN tiếng Việt 😀. " * 100
    title, content = payload["title"], payload["content"]
    source = f"{len(title.encode('utf-8'))}:{title}{len(content.encode('utf-8'))}:{content}"
    payload["sourceHash"] = hashlib.sha256(source.encode()).hexdigest()

    def prepare():
        request = urllib.request.Request(
            args.url + "/v1/knowledge-indexes:prepare", json.dumps(payload).encode(),
            {"Content-Type": "application/json", "Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    first, second = prepare(), prepare()
    assert first["profileHash"] == fixture["response"]["profileHash"]
    assert first["sourceHash"] == payload["sourceHash"]
    assert len(first["chunks"]) > 1
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    covered: set[int] = set()
    assert len(first["chunks"]) == len(second["chunks"])
    for left, right in zip(first["chunks"], second["chunks"], strict=True):
        assert left["chunkId"] == right["chunkId"]
        assert left["text"] == normalized[left["startChar"]:left["endChar"]]
        assert 0 < left["tokenCount"] <= 480
        covered.update(range(left["startChar"], left["endChar"]))
        vector = left["embedding"]
        assert len(vector) == 384 and all(math.isfinite(value) for value in vector)
        assert abs(sum(value * value for value in vector) - 1) < 0.002
        assert sum(abs(value) > 1e-6 for value in vector) > 100
        assert max(abs(a - b) for a, b in zip(vector, right["embedding"], strict=True)) < 1e-5
    assert all(i in covered for i, char in enumerate(normalized) if not char.isspace())
    print(f"PASS: real model, {len(first['chunks'])} chunks, dimension=384, stable rebuild")


if __name__ == "__main__":
    main()
