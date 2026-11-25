"""Đo p50/p95 và RSS của provider ml trong tiến trình (không gồm HTTP).

Số đo theo TL05 phải lấy trên máy đích. Chạy trên máy phát triển chỉ để tham khảo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import time
from pathlib import Path

import psutil

from supportflow_ai.adapters.classifiers.ml.provider import MlClassifier

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "evaluation" / "sample-classification.jsonl"


def percentile(values: list[float], q: float) -> float:
    """Phân vị theo nearest-rank."""
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    return ordered[max(1, math.ceil(q / 100 * len(ordered))) - 1]


async def run(model_dir: str, allow_dev_stub: bool, rounds: int, warmup: int) -> dict:
    load_start = time.perf_counter()
    provider = MlClassifier(
        model_dir=model_dir,
        allow_dev_stub=allow_dev_stub,
        max_concurrency=1,
        max_queue=0,
        queue_timeout_s=3.0,
    )
    if not provider.ready:
        raise SystemExit("provider chưa sẵn sàng: kiểm artifact hoặc cờ dev-stub")
    rows = [json.loads(line) for line in SAMPLES.read_text(encoding="utf-8").splitlines() if line]
    texts = [(row["title"], row["description"]) for row in rows]
    try:
        # Cold start: nạp artifact đến lần suy luận đầu tiên, đo riêng khỏi p50/p95.
        title, description = texts[0]
        await provider.classify(title=title, description=description)
        cold_start_ms = (time.perf_counter() - load_start) * 1000
        for title, description in texts * warmup:
            await provider.classify(title=title, description=description)
        latencies: list[float] = []
        for title, description in texts * rounds:
            start = time.perf_counter()
            await provider.classify(title=title, description=description)
            latencies.append((time.perf_counter() - start) * 1000)
    finally:
        provider.close()
    process = psutil.Process()
    return {
        "n": len(latencies),
        "warmupRounds": warmup,
        "coldStartMs": round(cold_start_ms, 1),
        "p50Ms": round(percentile(latencies, 50), 3),
        "p95Ms": round(percentile(latencies, 95), 3),
        "rssMb": round(process.memory_info().rss / 2**20, 1),
        "threads": process.num_threads(),
        "cpuCount": psutil.cpu_count(logical=True),
        "cpuModel": platform.processor(),
        "python": platform.python_version(),
        "samples": SAMPLES.name,
        "scope": "in-process classify(), không gồm HTTP",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--allow-dev-stub", action="store_true")
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    result = asyncio.run(run(args.model_dir, args.allow_dev_stub, args.rounds, args.warmup))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
